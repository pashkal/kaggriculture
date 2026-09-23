"""What does "sell X of product Y on turn Z" yield, in isolation?

Each query is evaluated against a market that has only been moved by town
consumption up to turn Z -- no other sales, and queries never see each other.
Units are quoted one at a time the way the env does, so a large sale walks its
own price down; a unit that quotes at the $1 floor adds no supply, so every
further unit also yields $1.

  sale_value.py MELON:100@266 --unlock PIZZA_SHOP,BAKERY,PIZZA_SHOP,YARN_STORE
  sale_value.py --sweep MELON --units 1,10,50,100 --turns 0,120,240
"""

import argparse
import sys

from market import PRICE_FLOOR, PRODUCTS, SHOPS, Market
from predict_prices import parse_inventory, parse_sale, simulate, unlock_schedule


def baseline(market, turns, unlocks):
    """Market state entering each turn, moved by town consumption only."""
    rows, _ = simulate(market.copy(), turns, (), unlocks)
    return rows


def quote(row, market_template, item, units):
    """Revenue for selling `units` of `item` into the turn `row` describes."""
    sim = market_template.copy()
    sim.inventory = dict(row["inventory"])
    sim.step = row["turn"] + market_template.step
    before = sim.price(item)
    per_unit = []
    for _ in range(units):
        price = sim.price(item)
        per_unit.append(price)
        if price > PRICE_FLOOR:
            sim.inventory[item] += 1
    return {
        "revenue": sum(per_unit),
        "units": units,
        "price_before": before,
        "price_after": sim.price(item),
        "first_unit": per_unit[0] if per_unit else 0,
        "last_unit": per_unit[-1] if per_unit else 0,
        "at_floor": sum(1 for p in per_unit if p <= PRICE_FLOOR),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sales", nargs="*", type=parse_sale, metavar="ITEM:UNITS@TURN",
                    help="a sale to value; repeatable, each evaluated in isolation")
    ap.add_argument("--sweep", default="", help="product to sweep instead of naming sales")
    ap.add_argument("--units", default="1,10,25,50,100", help="unit counts for --sweep")
    ap.add_argument("--turns", default="0,72,144,216", help="turns for --sweep")
    ap.add_argument("--start-day", type=int, default=0)
    ap.add_argument("--start-hour", type=int, default=0)
    ap.add_argument("--shops", default="", help="roster already unlocked at the start")
    ap.add_argument("--unlock", default="", help="shops unlocking during the window, in order")
    ap.add_argument("--inventory", nargs="*", default=[], metavar="ITEM=N")
    ap.add_argument("--shed-capacity", type=int, default=100,
                    help="flag sales above this; the shed caps what you can hold to sell (default 100)")
    args = ap.parse_args(argv)

    shops = [s.strip().upper() for s in args.shops.split(",") if s.strip()]
    queue = [s.strip().upper() for s in args.unlock.split(",") if s.strip()]
    for name in shops + queue:
        if name not in SHOPS:
            ap.error(f"unknown shop {name!r}; expected one of {', '.join(sorted(SHOPS))}")

    if args.sweep:
        item = args.sweep.strip().upper()
        if item not in PRODUCTS:
            ap.error(f"unknown product {item!r}")
        unit_list = [int(u) for u in args.units.split(",") if u.strip()]
        turn_list = [int(t) for t in args.turns.split(",") if t.strip()]
        sales = [(item, u, t) for t in turn_list for u in unit_list]
    elif args.sales:
        sales = args.sales
    else:
        ap.error("name at least one ITEM:UNITS@TURN, or use --sweep")

    market = Market(parse_inventory(args.inventory), shops,
                    day=args.start_day, hour=args.start_hour)
    horizon = max(t for _, _, t in sales) + 1

    schedule = unlock_schedule(market, horizon, queue)
    roster = ", ".join(shops) if shops else "none"
    print(f"Baseline: town consumption only, from day {args.start_day} "
          f"hour {args.start_hour}; shops at start: {roster}")
    if schedule:
        named = ", ".join(f"day {d}: {s}" for d, s in schedule if s)
        print(f"Unlocks in window: {named or 'none supplied'}")
    rows = baseline(market, horizon, schedule)

    if args.sweep:
        unit_list = sorted({u for _, u, _ in sales})
        print(f"{args.sweep.upper()} revenue by units sold (rows) and turn (columns)")
        print(f"{'units':>6} " + " ".join(f"{'t'+str(t):>12}" for t in turn_list))
        print(f"{'spot':>6} " + " ".join(f"{'$'+str(rows[t]['prices'][args.sweep.upper()]):>12}" for t in turn_list))
        for u in unit_list:
            cells = [f"${quote(rows[t], market, args.sweep.upper(), u)['revenue']:,}" for t in turn_list]
            print(f"{u:>6} " + " ".join(f"{c:>12}" for c in cells))
        return 0

    for item, units, turn in sales:
        q = quote(rows[turn], market, item, units)
        day, hour = divmod(turn + market.step, market.turns_per_day)
        print(f"Sell {units} {item} on turn {turn} (day {day}, hour {hour})")
        print(f"  revenue          ${q['revenue']:,}")
        print(f"  per unit         ${q['revenue'] / units:,.2f} average "
              f"(first ${q['first_unit']}, last ${q['last_unit']})")
        print(f"  spot x units     ${q['price_before'] * units:,}"
              f"  -> slippage ${q['price_before'] * units - q['revenue']:,}")
        print(f"  price {q['price_before']} -> {q['price_after']}"
              f"   inventory {rows[turn]['inventory'][item]} -> "
              f"{rows[turn]['inventory'][item] + units - q['at_floor']}")
        if q["at_floor"]:
            print(f"  !! {q['at_floor']} of {units} units quoted at the ${PRICE_FLOOR} floor")
        if units > args.shed_capacity:
            print(f"  !! {units} exceeds the shed capacity of {args.shed_capacity}; "
                  f"you cannot hold that much to sell in one turn")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())

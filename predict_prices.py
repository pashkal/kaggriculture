"""Predict market prices over the opening of a season.

By default this covers the first three days (72 turns) from a fresh market.
Note that no shops are unlocked during that window -- the first instance is
drawn at the start of day 3 -- so the baseline is the town center alone, which
takes one of every product except fertilizer once per day. Pass --shops for a
roster that is already unlocked, --unlock for the shops that will unlock during
the window (in order), or --start-day to look at a later window.

Player sales are not modelled: selling into the market raises inventory and
pushes prices the other way. Use --sell WHEAT:20@6 to fold a planned sale in.
"""

import argparse
import sys

from market import MAX_SHOP_INSTANCES, PRODUCTS, SHOPS, Market


def parse_sale(spec):
    """"WHEAT:20@6" -> ("WHEAT", 20, 6): sell 20 wheat at turn 6."""
    try:
        item, rest = spec.split(":", 1)
        units, _, turn = rest.partition("@")
        item = item.upper()
        if item not in PRODUCTS:
            raise ValueError(f"unknown product {item!r}")
        return item, int(units), int(turn or 0)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"bad --sell {spec!r} ({exc}); want ITEM:UNITS@TURN")


def parse_inventory(specs):
    """"WHEAT=9800" -> {"WHEAT": 9800}."""
    out = {}
    for spec in specs:
        item, _, amount = spec.partition("=")
        item = item.upper()
        if item not in PRODUCTS:
            raise argparse.ArgumentTypeError(f"unknown product {item!r}")
        out[item] = int(amount)
    return out


def unlock_schedule(market, turns, queue):
    """Days inside the window on which a queued shop unlocks, paired with it.

    The env unlocks at end-of-day, so a shop drawn for day D is first active at
    day D hour 0. Unlocks land on multiples of the unlock interval and stop once
    the town holds MAX_SHOP_INSTANCES.
    """
    interval = market.shop_unlock_interval
    count = len(market.shops)
    schedule, pending = [], list(queue)
    for t in range(turns):
        step = market.step + t
        day, hour = divmod(step, market.turns_per_day)
        if hour or day <= 0 or day % interval or count >= MAX_SHOP_INSTANCES:
            continue
        count += 1
        schedule.append((day, pending.pop(0) if pending else None))
    return schedule


def simulate(market, turns, sales=(), unlocks=()):
    """Step `turns` turns, returning one row per turn plus the sale revenues.

    A row is the state entering the turn, before that turn's town consumption
    -- the env processes player orders first, so this is the price a sale
    placed on that turn is quoted against. `unlocks` is a [(day, shop)] list as
    produced by `unlock_schedule`; each shop joins the roster at that day's
    hour 0, before it first consumes.
    """
    by_turn = {}
    for item, units, turn in sales:
        by_turn.setdefault(turn, []).append((item, units))

    due = {day: shop for day, shop in unlocks if shop}

    rows, revenues = [], []
    for t in range(turns):
        unlocked = None
        if market.hour == 0 and market.day in due:
            unlocked = due.pop(market.day)
            market.add_shop(unlocked)
        # The env runs player trades before the town consumes, so this is the
        # price a sale placed on this turn is actually quoted against.
        row = {
            "turn": t,
            "day": market.day,
            "hour": market.hour,
            "inventory": dict(market.inventory),
            "prices": market.prices,
            "unlocked": unlocked,
        }
        rows.append(row)
        for item, units in by_turn.get(t, []):
            revenues.append((t, item, units, market.sell(item, units)))
        row["consumed"] = market.consume()
        market.step = market.step + 1
    return rows, revenues


def print_table(rows, products, every):
    header = ["turn", "d:h"] + [p[:4] for p in products]
    widths = [4, 5] + [max(4, len(h)) for h in header[2:]]
    print("  ".join(h.rjust(w) for h, w in zip(header, widths)))
    print("  ".join("-" * w for w in widths))
    for row in rows:
        if row["unlocked"]:
            print(f"{'':>{widths[0]}}  {'':>{widths[1]}}  <- day {row['day']}: {row['unlocked']} unlocks")
        if row["turn"] % every and row is not rows[-1]:
            continue
        cells = [str(row["turn"]), f"{row['day']}:{row['hour']:02d}"]
        cells += [str(row["prices"][p]) for p in products]
        print("  ".join(c.rjust(w) for c, w in zip(cells, widths)))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--turns", type=int, default=None, help="turns to simulate (default 72 = 3 days)")
    ap.add_argument("--days", type=int, default=None, help="days to simulate, instead of --turns")
    ap.add_argument("--start-day", type=int, default=0)
    ap.add_argument("--start-hour", type=int, default=0)
    ap.add_argument("--shops", default="", help=f"roster already unlocked at the start, repeats allowed: {','.join(sorted(SHOPS))}")
    ap.add_argument("--unlock", default="", help="shops that unlock during the window, in unlock order "
                                                 "(comma-separated); one is consumed per unlock day")
    ap.add_argument("--inventory", nargs="*", default=[], metavar="ITEM=N",
                    help="starting inventory overrides (default: I0 = 10000 each)")
    ap.add_argument("--sell", type=parse_sale, action="append", default=[], metavar="ITEM:UNITS@TURN",
                    help="fold a planned sale into the forecast; repeatable")
    ap.add_argument("--every", type=int, default=4, help="print every Nth turn (default 4)")
    ap.add_argument("--products", default="", help="restrict the table to these products")
    ap.add_argument("--csv", action="store_true", help="emit CSV instead of a table")
    args = ap.parse_args(argv)

    shops = [s.strip().upper() for s in args.shops.split(",") if s.strip()]
    queue = [s.strip().upper() for s in args.unlock.split(",") if s.strip()]
    for name in shops + queue:
        if name not in SHOPS:
            ap.error(f"unknown shop {name!r}; expected one of {', '.join(sorted(SHOPS))}")
    products = [p.strip().upper() for p in args.products.split(",") if p.strip()] or PRODUCTS

    market = Market(parse_inventory(args.inventory), shops,
                    day=args.start_day, hour=args.start_hour)
    if args.turns is not None and args.days is not None:
        ap.error("pass --turns or --days, not both")
    turns = args.turns if args.turns is not None else (
        args.days * market.turns_per_day if args.days is not None else 72)

    schedule = unlock_schedule(market, turns, queue)
    start = market.copy()
    rows, revenues = simulate(market, turns, args.sell, schedule)

    if args.csv:
        w = ["turn", "day", "hour"] + [f"{p}_price" for p in products] + [f"{p}_inv" for p in products]
        print(",".join(w))
        for row in rows:
            print(",".join([str(row["turn"]), str(row["day"]), str(row["hour"])]
                           + [str(row["prices"][p]) for p in products]
                           + [str(row["inventory"][p]) for p in products]))
        return 0

    print(f"Forecast: {turns} turns ({turns / market.turns_per_day:g} days) "
          f"from day {args.start_day} hour {args.start_hour}")
    print(f"Shops at start: {', '.join(sorted(shops)) if shops else 'none unlocked'}"
          f"{'' if shops else f' (first unlock is day {start.next_unlock_day})'}")
    if schedule:
        named = [f"day {d}: {s}" for d, s in schedule if s]
        unnamed = [d for d, s in schedule if s is None]
        print(f"Unlocks in window: {', '.join(named) if named else 'none supplied'}")
        if unnamed:
            print(f"  ...plus unknown draws on day(s) {', '.join(map(str, unnamed))} "
                  f"-- not modelled; extend --unlock to cover them")
    if queue[len(schedule):]:
        print(f"Unused --unlock entries (unlock after this window): "
              f"{', '.join(queue[len(schedule):])}")
    print(f"Town demand/day at start: "
          f"{', '.join(f'{k} {v}' for k, v in sorted(start.daily_demand().items()))}")
    print(f"Town demand/day at end:   "
          f"{', '.join(f'{k} {v}' for k, v in sorted(market.daily_demand().items()))}")
    print()
    print_table(rows, products, max(1, args.every))
    print()

    print(f"{'product':12} {'start':>6} {'end':>6} {'move':>6}   {'inv start':>9} {'inv end':>8}")
    for p in products:
        p0, p1 = start.price(p), market.price(p)
        print(f"{p:12} {p0:>6} {p1:>6} {p1 - p0:>+6}   "
              f"{start.inventory[p]:>9} {market.inventory[p]:>8}")

    if revenues:
        print()
        for turn, item, units, revenue in revenues:
            print(f"turn {turn:>3}: sold {units:>4} {item:12} for ${revenue:<7,} "
                  f"(${revenue / units:.1f}/unit, price now ${market.price(item)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

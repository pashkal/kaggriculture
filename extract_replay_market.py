"""Pull the market state on every turn out of a replay into a CSV.

One row per turn, holding the observation as it stood entering that turn:
each product's price and market inventory, plus the town's unlocked shops.
"""

import argparse
import csv
import json
import sys

from market import PRODUCTS


def rows_from_replay(replay):
    """Yield one dict per turn. Agent 0 carries the shared market and town."""
    for index, step in enumerate(replay["steps"]):
        obs = step[0]["observation"]
        market = obs["market"]
        shops = obs.get("town", {}).get("unlocked_shops", [])
        row = {
            "step": obs.get("step", index),
            "day": obs.get("day", 0),
            "hour": obs.get("hour", 0),
            "n_shops": len(shops),
            "shops": ";".join(shops),
        }
        for item in PRODUCTS:
            row[f"{item}_price"] = market["prices"].get(item)
            row[f"{item}_inv"] = market["inventory"].get(item)
        yield row


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("replay", nargs="?", default="replay.json")
    ap.add_argument("-o", "--out", default="replay_market.csv")
    args = ap.parse_args(argv)

    with open(args.replay) as fh:
        replay = json.load(fh)
    rows = list(rows_from_replay(replay))
    if not rows:
        print(f"{args.replay}: no steps found", file=sys.stderr)
        return 1

    fields = ["step", "day", "hour", "n_shops", "shops"]
    fields += [f"{item}_{kind}" for item in PRODUCTS for kind in ("price", "inv")]
    with open(args.out, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    last = rows[-1]
    print(f"{args.out}: {len(rows)} turns (day {rows[0]['day']} hour {rows[0]['hour']} "
          f"-> day {last['day']} hour {last['hour']})")
    print(f"final shops ({last['n_shops']}): {last['shops'] or 'none'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

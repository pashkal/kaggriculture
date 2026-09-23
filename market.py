"""Market/town-consumption simulator.

Mirrors the env's town model (see the "Town Buildings" section of `pricing`):
one absolute turn counter `step = day * turns_per_day + hour` drives everything.
Every shop instance consumes one of each product it demands when
`step % shop_sell_interval == 0` (single-product shops consume 2x), and the town
center consumes one of every product except fertilizer when
`step % center_sell_interval == 0`.
"""

from collections import Counter

from pricing_function import MARKET_PARAMS, get_price

PRODUCTS = ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON", "EGG", "MILK", "WOOL", "FERTILIZER"]

SHOPS = {
    "BAKERY":         ["EGG", "WHEAT"],
    "PIZZA_SHOP":     ["MILK", "TOMATO", "WHEAT"],
    "BRUNCH_SPOT":    ["EGG", "WHEAT", "STRAWBERRY"],
    "YARN_STORE":     ["WOOL"],
    "ICE_CREAM_SHOP": ["STRAWBERRY", "MILK", "WHEAT"],
    "PET_CAFE":       ["CARROT"],
    "SMOOTHIE_SHOP":  ["STRAWBERRY", "MILK"],
    "FARMERS_MARKET": ["WHEAT", "CARROT", "TOMATO", "STRAWBERRY"],
}

TOWN_CENTER_PRODUCTS = [p for p in PRODUCTS if p != "FERTILIZER"]

MAX_SHOP_INSTANCES = 8
PRICE_FLOOR = 1


class Sale:
    def __init__(self, crop: str, units: int, turn: int):
        self.crop = crop
        self.units = units
        self.turn = turn



class Market:
    """Market inventory + town demand at a point in time.

    inventory: amounts of every product, as {"WHEAT": 10000, ...}. Missing
        products fall back to their I0 (the equilibrium, where price == base).
    shops: the unlocked shop instances. Shops are drawn with replacement, so
        duplicates matter and each copy consumes independently — pass a list
        (["BAKERY", "BAKERY"]) or counts ({"BAKERY": 2}). A plain set is
        accepted but can only express one instance of each.
    day, hour: the current turn, as reported in the observation.
    """

    def __init__(self, inventory, shops=(), day=0, hour=0, turns_per_day=24,
                 shop_sell_interval=4, center_sell_interval=24,
                 shop_unlock_interval=3, params=None):
        self.inventory = {item: int(inventory.get(item, MARKET_PARAMS[item]["I0"]))
                          for item in PRODUCTS}
        self.shops = self._as_instances(shops)
        self.turns_per_day = max(1, int(turns_per_day))
        self.day = int(day)
        self.hour = int(hour)
        self.shop_sell_interval = max(1, int(shop_sell_interval))
        self.center_sell_interval = max(1, int(center_sell_interval))
        self.shop_unlock_interval = max(1, int(shop_unlock_interval))
        self.params = params

    @staticmethod
    def _as_instances(shops):
        """Normalise a list / set / {name: count} mapping into a flat list."""
        if isinstance(shops, dict):
            pairs = shops.items()
        elif isinstance(shops, Counter):
            pairs = shops.items()
        else:
            pairs = Counter(shops).items()
        out = []
        for name, count in pairs:
            if name not in SHOPS:
                raise ValueError(f"unknown shop {name!r}; expected one of {sorted(SHOPS)}")
            out.extend([name] * int(count))
        return out

    # --- where we are in the season ---------------------------------------

    @property
    def step(self):
        """Absolute turn index; the quantity every interval is measured against."""
        return self.day * self.turns_per_day + self.hour

    @step.setter
    def step(self, value):
        value = int(value)
        self.day, self.hour = divmod(value, self.turns_per_day)

    # --- prices ------------------------------------------------------------

    def price(self, item):
        return get_price(item, self.inventory[item], self.params)

    @property
    def prices(self):
        return {item: self.price(item) for item in PRODUCTS}

    # --- demand ------------------------------------------------------------

    def demand_at(self, step=None):
        """Units of each product the town removes on `step` (default: now).

        Only products actually consumed on that step appear in the result.
        """
        step = self.step if step is None else int(step)
        demand = Counter()
        if step % self.shop_sell_interval == 0:
            for name in self.shops:
                products = SHOPS[name]
                multiplier = 2 if len(products) == 1 else 1
                for item in products:
                    demand[item] += multiplier
        if step % self.center_sell_interval == 0:
            for item in TOWN_CENTER_PRODUCTS:
                demand[item] += 1
        return dict(demand)

    def daily_demand(self):
        """Units of each product the town removes over a full day at the
        current shop roster (the per-day rate the doc quotes: 6 per shop per
        product at the default intervals, plus 1 from the town center)."""
        total = Counter()
        for hour in range(self.turns_per_day):
            total.update(self.demand_at(self.day * self.turns_per_day + hour))
        return dict(total)

    # --- simulation --------------------------------------------------------

    def consume(self):
        """Apply the town consumption due at the current step.

        Returns what was consumed. Inventory is allowed to go below zero, as in
        the env — scarcity is expressed through the price curve, not a stockout.
        """
        demand = self.demand_at()
        for item, units in demand.items():
            self.inventory[item] -= units
        return demand

    def advance(self, turns=1):
        """Run `turns` turns forward, consuming at each one.

        Ordering matches the env: consumption for a step is applied during that
        step, then the clock moves on. Shops that unlock at the end of a day are
        not modelled here (the draw is random and seeded) — call `add_shop` when
        the observation shows a new one.
        """
        for _ in range(int(turns)):
            self.consume()
            self.step = self.step + 1
        return self

    def add_shop(self, name):
        """Unlock one more shop instance, respecting the 8-instance cap."""
        if name not in SHOPS:
            raise ValueError(f"unknown shop {name!r}; expected one of {sorted(SHOPS)}")
        if len(self.shops) >= MAX_SHOP_INSTANCES:
            return False
        self.shops.append(name)
        return True

    @property
    def next_unlock_day(self):
        """Day the next shop instance unlocks, or None once the cap is hit."""
        if len(self.shops) >= MAX_SHOP_INSTANCES:
            return None
        interval = self.shop_unlock_interval
        return (self.day // interval + 1) * interval

    # --- trading against the curve ----------------------------------------

    def sell(self, item, units=1):
        """Sell `units` into the market one at a time, as the env does, and
        return the total revenue. Each unit is quoted at the current inventory
        and then raises it, so a big sale walks its own price down. A unit sold
        at the $1 floor adds no supply."""
        revenue = 0
        for _ in range(int(units)):
            price = self.price(item)
            revenue += price
            if price > PRICE_FLOOR:
                self.inventory[item] += 1
        return revenue

    def sell_quote(self, item, units=1, day=None, hour=None):
        """Revenue from selling `units` without mutating the market.

        With `day` and/or `hour`, quote a future turn instead of now: the town
        is run forward to that turn first, so the answer reflects the scarcity
        it will have created by then. Either one alone is taken relative to the
        current turn, so `hour=12` means noon today and `day=5` means day 5 at
        the current hour. The target must not be in the past.

        The shop roster is held fixed, as in `advance` -- shops that would
        unlock along the way are a random draw, so add them with `add_shop`
        first if you want them counted.
        """
        sim = self.copy()
        if day is not None or hour is not None:
            target = (self.day if day is None else int(day)) * self.turns_per_day \
                     + (self.hour if hour is None else int(hour))
            if target < self.step:
                raise ValueError(f"day/hour resolve to step {target}, before the "
                                 f"current step {self.step}; quotes only look forward")
            sim.advance(target - self.step)
        return sim.sell(item, units)

    def buy(self, item, units=1):
        """Buy `units` out of the market and return the total cost. Quoted at
        post-buy inventory, so a buy/sell round-trip nets zero."""
        cost = 0
        for _ in range(int(units)):
            cost += get_price(item, self.inventory[item] - 1, self.params)
            self.inventory[item] -= 1
        return cost

    # --- plumbing ----------------------------------------------------------

    def copy(self):
        return Market(dict(self.inventory), list(self.shops), self.day, self.hour,
                      self.turns_per_day, self.shop_sell_interval,
                      self.center_sell_interval, self.shop_unlock_interval,
                      self.params)

    @classmethod
    def from_observation(cls, obs, configuration=None):
        """Build from a kaggriculture observation (and optional configuration)."""
        cfg = configuration or {}
        def get(key, default):
            if isinstance(cfg, dict):
                return cfg.get(key, default)
            return getattr(cfg, key, default)
        market = obs["market"] if isinstance(obs, dict) else obs.market
        town = obs["town"] if isinstance(obs, dict) else obs.town
        day = (obs["day"] if isinstance(obs, dict) else obs.day) or 0
        hour = (obs["hour"] if isinstance(obs, dict) else getattr(obs, "hour", 0)) or 0
        return cls(
            dict(market["inventory"]),
            list(town.get("unlocked_shops", [])),
            day, hour,
            turns_per_day=get("turnsPerDay", 24),
            shop_sell_interval=get("townShopSellInterval", 4),
            center_sell_interval=get("townCenterSellInterval", 24),
            shop_unlock_interval=get("townShopUnlockInterval", 3),
            params=market.get("params"),
        )

    def __repr__(self):
        return (f"Market(day={self.day}, hour={self.hour}, step={self.step}, "
                f"shops={sorted(Counter(self.shops).items())})")

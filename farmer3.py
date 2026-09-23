# Only operating on one-off plants (WHEAT, CARROT, MELON)
# Predicting prices and picking the "most money per turn" crop to plant

import random
from collections import defaultdict

from market import Market, Sale

LOOPS = [
    [(1, 4), (0, 4), (0, 3), (0, 2), (0, 1), (0, 0)],
    [(2, 4), (2, 3), (1, 3), (1, 2), (1, 1), (1, 0)],
    [(3, 4), (3, 3), (3, 2), (2, 2), (2, 1), (2, 0)],
    [(4, 4), (4, 3), (4, 2), (4, 1), (4, 0), (3, 0)], #, (3, 1)]
]

CROPS_MAX_YIELD = {"WHEAT": 4, "CARROT": 3, "TOMATO": 4, "STRAWBERRY": 4, "MELON": 6}
AGE_TO_FIRST_YIELD = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10, "GOOSE": 4, "COW": 8, "SHEEP": 6}
AGE_TO_MAX_YIELD = {"WHEAT": 4, "CARROT": 3, "MELON": 10, "TOMATO": 11, "STRAWBERRY": 16}


# CROP_DISTRIBUTION = [0.30, 0.15, 0.10, 0.10, 0.10, 0.1, 0.1, 0.05]
CROP_DISTRIBUTION = [0.33, 0.33, 0.0, 0.0, 0.34, 0.0, 0.0, 0.0]

SEED_PRICE = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80, "GOOSE": 300, "COW": 400, "SHEEP": 500}

PLANTS = {"WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"}
ANIMALS = {"GOOSE", "COW", "SHEEP"}

ANIMALS_NEED = {"COOP": ["GOOSE"], "PASTURE": ["COW", "SHEEP"]}

def towards(x, y, nx, ny):
    if nx < x:
        return "WEST"
    if nx > x:
        return "EAST"
    if ny < y:
        return "NORTH"
    if ny > y:
        return "SOUTH"    
    return "PASS"

def on_loop(loop: list[(int, int)], x: int, y: int):
    for nx, ny in loop:
        if x == nx and y == ny:
            return True
    return False

def next_on_loop(loop: list[(int, int)], x: int, y: int):
    for i in range(0, len(loop) - 1):
        if x == loop[i][0] and y == loop[i][1]:
            return loop[i + 1]
    return (None, None)

def get_direction(loop: list[(int, int)], x: int, y: int):
    print(f"Looking for next tile for ({x},{y})")
    nx, ny = next_on_loop(loop, x, y)
    if nx is None and ny is None:
        return "PASS"
    print(f"Found ({nx}, {ny})")
    return towards(x, y, nx, ny)

def my_agent(obs):
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    shed = private["shed"]
    fx, fy = me["farmer"]
    day = obs["day"]
    hour = obs["hour"]
    money_left = me["money"]
    print(f"========  Day {day + 1}, turn {hour + 1} ============")

    market_ops = []
    
    # Hour 0: just shopping and hiring
    if hour == 0:
        market = Market.from_observation(obs)
        market_ops.extend([["HIRE"], ["HIRE"], ["HIRE"]])
        empty_spaces = 0
        planned_sales: list[Sale] = []
        for i in range(5):
            for j in range(5):
                tile = me["tiles"][i][j]
                if i == 1 and j == 3:
                    continue
                if tile == None or tile["kind"] == "WEED" or (tile["kind"] == "PLANT" and day - tile["planted_day"] >= AGE_TO_FIRST_YIELD[tile["crop"]] and tile["yield_units"] >= CROPS_MAX_YIELD[tile["crop"]] - 1):
                    empty_spaces += 1
                if tile != None and tile["kind"] == "PLANT":
                    planned_sales.append(Sale(
                        tile["crop"],
                        CROPS_MAX_YIELD[tile["crop"]],
                        24 * (tile["planted_day"] + AGE_TO_MAX_YIELD[tile["crop"]] + 1) + 2,
                    ))

        shopping_list = defaultdict(int)
        print(f"{empty_spaces} empty spaces")

        previous_sales = planned_sales.copy()

        for i in range(empty_spaces):
            print(f"Deciding seed {i}")

            best_crop = None
            best_profit_per_day = -1000
            for crop in AGE_TO_MAX_YIELD.keys():
                amount = CROPS_MAX_YIELD[crop]
                sale_day = day + AGE_TO_FIRST_YIELD[crop] + 1
                if sale_day >= 29:
                    continue
                seed_price = SEED_PRICE[crop]

                copied_market = market.copy()
                for sale in sorted(previous_sales, key = lambda sale: sale.turn):
                    # print(f"Moving past a sale of {sale.units} units of {sale.crop} on turn {sale.turn}")
                    if sale.turn > sale_day * 24 + 2:
                        break
                    if sale.turn > copied_market.step:
                        print(f"Advanving market to step {sale.turn}")
                    while copied_market.step < sale.turn:
                        copied_market.advance()
                    copied_market.sell(sale.crop, sale.units)
                    
                revenue = copied_market.sell_quote(crop, amount, sale_day, 2) 
                profit = revenue - seed_price

                profit_per_day = profit * 1.0 / AGE_TO_MAX_YIELD[crop]
                print(f"Considering {crop}")
                print(f"Will sell {amount} of {crop} on day {sale_day + 1} for ${revenue}, profit will be {profit}, profit/day will be {profit * 1.0 / AGE_TO_MAX_YIELD[crop]}")
                if profit_per_day > best_profit_per_day:
                    best_crop = crop
                    best_profit_per_day = profit_per_day
            
            if best_crop != None:
                print(f"Settled on {best_crop} with ${best_profit_per_day} profit per day")
                shopping_list[best_crop] += 1

                print(f"Recording a sale of {CROPS_MAX_YIELD[best_crop]} units of {best_crop} on turn {24 * (day + AGE_TO_MAX_YIELD[best_crop] + 1) + 2}")
                previous_sales.append(Sale(best_crop, CROPS_MAX_YIELD[best_crop], 24 * (day + AGE_TO_MAX_YIELD[best_crop] + 1) + 2))
            else:
                print(f"Too late to plant anything")

        for crop in shopping_list:
            if crop in PLANTS:
                market_ops.append(["BUY_SEED", crop, shopping_list[crop]])
            else:
                market_ops.append(["BUY_ANIMAL", crop, shopping_list[crop]])

        print(market_ops)
        return {"farmer": ["PASS"], "hands": [], "market": market_ops}
    
    for product in shed:
        if shed[product] > 0:
            market_ops.append(["SELL", product, shed[product]])

    # Hour 1+: move and do actions
    hands: list[(int, int)] = me["hands"]
    print(hands)
    hand_actions = []
    seeds = private["seeds"]
    for i in range(1 + len(hands)):
        x, y = fx, fy
        if i > 0:
            x, y = hands[i - 1][0], hands[i - 1][1]
        print(f"Processing hand #{i+1} at ({x}, {y})")
        inventory = private["inventories"][i]
        print(f"{inventory}")
        if not on_loop(LOOPS[i], x, y):
            hand_actions.append([towards(x, y, LOOPS[i][0][0], LOOPS[i][0][1])])
            continue
        
        tile = me["tiles"][y][x]

        if tile is not None and tile["kind"] == "WEED":
            hand_actions.append(["DIG"])
            continue
        
        if tile is None:
            print(seeds)
            if "COW" in inventory and inventory["COW"] > 0 or "SHEEP" in inventory and inventory["SHEEP"] > 0:
                hand_actions.append(["BUILD_PASTURE"])
                continue
            if "GOOSE" in inventory and inventory["GOOSE"] > 0:
                hand_actions.append(["BUILD_COOP"])
                continue
            for plant in PLANTS:
                print(f"{seeds[plant]} of {plant} seeds left")
                if seeds[plant] > 0:
                    hand_actions.append(["PLANT", plant])
                    seeds[plant] -= 1
                    break
            if len(hand_actions) > i:
                continue
            hand_actions.append([get_direction(LOOPS[i], x, y)])
            continue
            # raise Exception(f"Not doing anything with empty tile at ({x}, {y})")
        
        if tile["kind"] == "COOP" and "animal" not in tile:
            if "GOOSE" not in inventory or inventory["GOOSE"] < 1:
                # raise Exception(f"No GOOSE for empty COOP at ({x}, {y}) on day {day + 1}, hour {hour + 1}")
                hand_actions.append(["PLACE", "GOOSE"])
            continue
        
        if tile["kind"] == "PASTURE" and "animal" not in tile:
            if ("COW" not in inventory or inventory["COW"] < 1) and ("SHEEP" not in inventory or inventory["SHEEP"] < 1):
                continue
                # raise Exception(f"No COW or SHEEP for empty PASTURE at ({x}, {y}) on day {day + 1}, hour {hour + 1}")
            if "COW" in inventory and inventory["COW"] > 0:
                hand_actions.append(["PLACE", "COW"])
                continue
            if "SHEEP" in inventory and inventory["SHEEP"] > 0:
                hand_actions.append(["PLACE", "SHEEP"])
                continue

        if "animal" in tile and tile["consecutive_unfed"] == 1 and not tile["fed_today"]:
            print(tile["consecutive_unfed"])
            if "WHEAT" not in inventory or inventory["WHEAT"] == 0:
                raise Exception(f"No WHEAT for feeding")
            hand_actions.append(["FEED"])
            continue

        if "animal" in tile and not tile["cared_today"]:
            hand_actions.append(["CARE"])
            continue

        if tile["kind"] == "PLANT":        
            crop_age = day - tile["planted_day"]
            if crop_age >= AGE_TO_FIRST_YIELD[tile["crop"]] and tile["yield_units"] >= CROPS_MAX_YIELD[tile["crop"]]:
                hand_actions.append(["HARVEST"])
                continue
            if tile["crop"] in ["TOMATO", "STRAWBERRY"] and crop_age >= AGE_TO_MAX_YIELD[tile["crop"]]:
                hand_actions.append(["DIG"])
                continue
            if not tile["watered_today"]:
                hand_actions.append(["WATER"])
                continue

        if "animal" in tile:
            animal_age = day - tile["placed_day"]
            if animal_age >= AGE_TO_FIRST_YIELD[tile["animal"]] and tile["yield_units"] >= 1:
                hand_actions.append(["HARVEST"])
                continue
        
        hand_actions.append([get_direction(LOOPS[i], x, y)])

    print(hand_actions)
    return {"farmer": hand_actions[0], "hands": hand_actions[1:], "market": market_ops}


import random
from collections import defaultdict

LOOPS = [
    [(1, 4), (0, 4), (0, 3), (0, 2), (0, 1), (0, 0)],
    [(2, 4), (2, 3), (1, 3), (1, 2), (1, 1), (1, 0)],
    [(3, 4), (3, 3), (3, 2), (2, 2), (2, 1), (2, 0)],
    [(4, 4), (4, 3), (4, 2), (4, 1), (4, 0), (3, 0), (3, 1)],
]

CROPS_MAX_YIELD = {"WHEAT": 4, "CARROT": 3, "TOMATO": 4, "STRAWBERRY": 4, "MELON": 6}
AGE_TO_FIRST_YIELD = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10, "GOOSE": 4, "COW": 8, "SHEEP": 6}
# CROP_DISTRIBUTION = [0.30, 0.15, 0.10, 0.10, 0.10, 0.1, 0.1, 0.05]
CROP_DISTRIBUTION = [0.0, 0.0, 0.0, 0.0, 1, 0.0, 0.0, 0.0]

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
    
def get_crop_from_distribution():
    crop_list = list(AGE_TO_FIRST_YIELD.keys())
    number = random.random()
    for i in range(len(CROP_DISTRIBUTION)):
        if number < CROP_DISTRIBUTION[i]:
            return crop_list[i]
        else:
            number -= CROP_DISTRIBUTION[i]

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

    market = []
    budget = 0
    
    # Hour 0: just shopping and hiring
    if hour == 0:
        market.extend([["HIRE"], ["HIRE"], ["HIRE"]])
        budget = 4
        empty_spaces = 0
        wheat_needed = 0
        for i in range(5):
            for j in range(5):
                tile = me["tiles"][i][j]
                if tile == None or tile["kind"] == "WEED":
                    empty_spaces += 1
                if tile is not None and "animal" in tile:
                    wheat_needed += 1
        
        wheat_in_shed = private["shed"].get("WHEAT", 0)
        if wheat_in_shed < wheat_needed:
            market.append(["BUY_PRODUCT", "WHEAT", wheat_needed - wheat_in_shed])

        shopping_list = defaultdict(int)
        print(f"{empty_spaces} empty spaces")
        if empty_spaces > 0:
            attempts = 0
            while (len(shopping_list) == 0 or len(shopping_list) == 8) and (attempts < 10):
                attempts += 1
                shopping_list = defaultdict(int)            
                for i in range(empty_spaces):
                    print(f"Buying seed #{i + 1}")
                    counter = 0
                    while True and counter < 50:
                        desired_crop = get_crop_from_distribution()
                        if budget + SEED_PRICE[desired_crop]  + (empty_spaces - i) * 20 < money_left:
                            print(f"Buying {desired_crop}")
                            shopping_list[desired_crop] += 1
                            budget += SEED_PRICE[desired_crop]
                            print(f"Current spend: {budget}")
                            break
                        counter += 1
                    if counter == 50:
                        shopping_list = {}
                        budget = 4
                        break
                

            for crop in shopping_list:
                if crop in PLANTS:
                    market.append(["BUY_SEED", crop, shopping_list[crop]])
                else:
                    market.append(["BUY_ANIMAL", crop, shopping_list[crop]])

        print(market)
        return {"farmer": ["PASS"], "hands": [], "market": market}
    
    # Hour 1: pick up animals
    if hour == 1:
        print(shed)
        hand_actions = []
        for i in range(4):
            empty_spaces = 0
            for cell in LOOPS[i]:
                tile = me["tiles"][cell[1]][cell[0]]
                if tile is None or tile["kind"] == "WEED":
                    empty_spaces += 1
            print(f"Hand {i + 1}, {empty_spaces} empty spaces")
            for animal in ANIMALS:
                if shed[animal] > 0 and shed[animal] <= empty_spaces:
                    hand_actions.append(["PICKUP", animal, shed[animal]])
                    shed[animal] = 0
                    break
            if len(hand_actions) > i:
                continue
            hand_actions.append(["PASS"])

        for product in shed:
            if product != "WHEAT" and shed[product] > 0:
                market.append(["SELL", product, shed[product]])

        print(hand_actions)    
        return {"farmer": hand_actions[0], "hands": hand_actions[1:], "market": market}

    # Hour 2: pick up wheat if necessary, sell the rest
    if hour == 2:
        total_wheat = 0
        print(shed)
        hand_actions = []
        for i in range(4):
            wheat_to_pickup = 0
            empty_spaces = 0
            for cell in LOOPS[i]:
                tile = me["tiles"][cell[1]][cell[0]]
                if tile is not None and "animal" in tile:
                    wheat_to_pickup += 1
            total_wheat += wheat_to_pickup
            print(f"Hand {i + 1}, {empty_spaces} empty spaces")
            if wheat_to_pickup > 0:
                hand_actions.append(["PICKUP", "WHEAT", wheat_to_pickup])
            if len(hand_actions) > i:
                continue
            hand_actions.append(["PASS"])
        if shed["WHEAT"] > total_wheat:
            market.append(["SELL", "WHEAT", shed["WHEAT"] - total_wheat])
        print(hand_actions)    
        return {"farmer": hand_actions[0], "hands": hand_actions[1:], "market": market}

    # Hour 3+: move and do actions
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

        if tile["kind"] == "PLANT" and not tile["watered_today"]:
            hand_actions.append(["WATER"])
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
            if crop_age >= AGE_TO_FIRST_YIELD[tile["crop"]] and tile["yield_units"] >= 1:
                hand_actions.append(["HARVEST"])
                continue
            
        if "animal" in tile:
            animal_age = day - tile["placed_day"]
            if animal_age >= AGE_TO_FIRST_YIELD[tile["animal"]] and tile["yield_units"] >= 1:
                hand_actions.append(["HARVEST"])
                continue
        
        hand_actions.append([get_direction(LOOPS[i], x, y)])

    print(hand_actions)
    return {"farmer": hand_actions[0], "hands": hand_actions[1:], "market": market}


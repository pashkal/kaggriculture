import random
from collections import defaultdict

LOOPS = [
    [(1, 4), (0, 4), (0, 3), (0, 2), (0, 1), (0, 0)],
    [(2, 4), (2, 3), (1, 3), (1, 2), (1, 1), (1, 0)],
    [(3, 4), (3, 3), (3, 2), (2, 2), (2, 1), (2, 0)],
    [(4, 4), (4, 3), (4, 2), (4, 1), (4, 0), (3, 0), (3, 1)]
]

CROPS_MAX_YIELD = {"WHEAT": 4, "CARROT": 3, "TOMATO": 4, "STRAWBERRY": 4, "MELON": 6}
AGE_TO_FIRST_YIELD = {"WHEAT": 2, "CARROT": 2, "TOMATO": 8, "STRAWBERRY": 10, "MELON": 10, "GOOSE": 4, "COW": 8, "SHEEP": 6}
CROP_DISTRIBUTION = [0.15, 0.15, 0.15, 0.15, 0.15, 0.1, 0.1, 0.05]
SEED_PRICE = {"WHEAT": 10, "CARROT": 20, "TOMATO": 50, "STRAWBERRY": 100, "MELON": 80, "GOOSE": 300, "COW": 400, "SHEEP": 500}

PLANTS = {"WHEAT", "CARROT", "TOMATO", "STRAWBERRY", "MELON"}
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

def get_pasture_animal_from_distribution():
    number = random.random()
    if number < CROP_DISTRIBUTION[6] / (CROP_DISTRIBUTION[6] + CROP_DISTRIBUTION[7]):
        return "COW"
    else:
        return "SHEEP"


def get_next_action(day, desired_crop, tile):
    if tile is None:
        if desired_crop in PLANTS:
            return ["PLANT", desired_crop]
        if desired_crop in ANIMALS_NEED["COOP"]:
            return ["BUILD_COOP"]
        if desired_crop in ANIMALS_NEED["PASTURE"]:
            return ["BUILD_PASTURE"]
    print(desired_crop)
    if tile["kind"] == "WEED":
        return ["DIG"]
    
    if tile["kind"] == 'COOP' or tile["kind"] == 'PASTURE':
        if desired_crop not in ANIMALS_NEED[tile["kind"]]:
            raise Exception(f"COOP where desired crop is {desired_crop}")
        if "animal" not in tile:
            return ["PLACE", desired_crop]
        if tile["animal"] != desired_crop:
            animal = tile["animal"]
            raise Exception(f"{animal} where desired crop is {desired_crop}")
        
        if tile["consecutive_unfed"] >= 1:
            return ["FEED"]
        if not tile["cared_today"]:
            return ["CARE"]
        if day - tile["placed_day"] >= AGE_TO_FIRST_YIELD[desired_crop] and tile["yield_units"] >= 1:
            return ["HARVEST"]
    
    if tile["kind"] == "plant":
        if tile["crop"] != desired_crop:
            crop = tile["crop"]
            raise Exception(f"{crop} where {desired_crop} should be")
        
        if not tile["watered_today"]:
            return ["WATER"]
        
        crop_age = day - tile["planted_day"]
        if crop_age >= AGE_TO_FIRST_YIELD[crop] and tile["yield_units"] >= CROPS_MAX_YIELD[crop]:
            return ["HARVEST"]
        

def get_action(day, loop, fx, fy, tiles) -> list[str]:
    if not on_loop(loop, fx, fy):
        return [towards(fx, fy, loop[0][0], loop[0][1])]

    tile = tiles[fy][fx]

    # If standing on an empty tile, plant wheat
    desired_crop = get_crop_from_distribution()
    if tile != None:
      if tile["kind"] == "plant":
          desired_crop = tile["crop"]
      else:
          if "animal" in tile and tile["animal"] != None:
              desired_crop = tile["animal"]
          if tile["kind"] == "COOP":            
              desired_crop = "GOOSE"
          else:
              desired_crop = get_pasture_animal_from_distribution()
    
      if tile["kind"] == "WEED":
          return ["DIG"]
    
    next_action = get_next_action(day, desired_crop, tile)
    if next_action != None:
        return next_action
    else:
        return [get_direction(loop, fx, fy)]

def my_agent(obs):
    player = obs["player"]
    me = obs["farms"][player]
    private = obs["private"]
    fx, fy = me["farmer"]
    day = obs["day"]
    hour = obs["hour"]
    money_left = me["money"]
    print(f"========  Day {day + 1}, turn {hour + 1} ============")

    market = []
    budget = 0
    shopping_list = defaultdict(int)
    
    if hour == 0:
        market.extend([["HIRE"], ["HIRE"], ["HIRE"]])
        empty_spaces = 0
        for i in range(5):
            for j in range(5):
                tile = me["tiles"][i][j]
                if tile == None or tile["kind"] == "WEED":
                    empty_spaces += 1
                while True:
                  desired_crop = get_crop_from_distribution()
                  if budget + SEED_PRICE[desired_crop] < money_left:
                      shopping_list[desired_crop] += 1
                      break
        for crop in shopping_list:
            if crop in PLANTS:
                market.extend(["BUY_SEED", crop, shopping_list[crop]])
            else:
                market.extend(["BUY", crop, shopping_list[crop]])
        
                
    for crop in PLANTS:
      wheat_seeds = private["seeds"].get(crop)
      print(f"Have {wheat_seeds} {crop} seeds")
      # Buy a wheat seed if we have none and have enough money
      if private["seeds"].get(crop, 1) < 1 and me["money"] >= 10:
          market.append(["BUY_SEED", crop, 4 - private["seeds"].get(crop, 1)])

      # Sell any wheat sitting in the shed
      crop_in_shed = private["shed"].get(crop, 0)
      if crop_in_shed > 0:
          market.append(["SELL", crop, crop_in_shed])
    
    for animal in ["COW", "SHEEP", "GOOSE"]:
        if private["shed"].get(animal) == 0:
            market.append(["BUY_ANIMAL", animal, 1])

    if len(me["hands"]) == 0:
        market.extend([["HIRE"], ["HIRE"], ["HIRE"]])

    hands: list[(int, int)] = me["hands"]
    hands.insert(0, (fx, fy))    
    print(hands)
    hand_actions = []
    for i in range(len(hands)):
        hand_actions.append(get_action(day, LOOPS[i], hands[i][0], hands[i][1], me["tiles"]))
    
    print(hand_actions)
    
    return {"farmer": hand_actions[0], "hands": hand_actions[1:], "market": market}

    

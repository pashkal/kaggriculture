from kaggle_environments import make
import json


def my_agent(obs):
    player = obs["player"]
    me = obs["farms"][player]
    fx, fy = me["farmer"]
    tile = me["tiles"][fy][fx]    
    private = obs["private"]

    market = []
    if private["seeds"].get("WHEAT", 0) == 0 and me["money"] >= 10:
        market.append(["BUY_SEED", "WHEAT", 1])

    # Sell any wheat sitting in the shed
    wheat_in_shed = private["shed"].get("WHEAT", 0)
    if wheat_in_shed > 0:
        market.append(["SELL", "WHEAT", wheat_in_shed])
    

    # If standing on an empty tile, plant wheat
    if tile is None and private["seeds"].get("WHEAT", 0) > 0:
        return {"farmer": ["PLANT", "WHEAT"], "hands": [], "market": market}

    # If standing on a plant, manage watering and harvesting
    if isinstance(tile, dict) and tile.get("kind") == "PLANT":
        crop_age = obs["day"] - tile["planted_day"]
        if crop_age >= 2 and tile["yield_units"] > 2:  # Wheat first_yield_day = 2
            return {"farmer": ["HARVEST"], "hands": [], "market": market}
        if not tile["watered_today"]:
            return {"farmer": ["WATER"], "hands": [], "market": market}

    return {"farmer": ["PASS"], "hands": [], "market": market}

configuration = {"episodeSteps": 720}

env = make("kaggriculture", configuration, debug=True)
env.run([my_agent, "pass"])

with open("replay.json", "w") as f:
    json.dump(env.toJSON(), f)

html = env.render(mode="html", width=1200, height=800)
with open("replay.html", "w") as f:
    f.write(html)
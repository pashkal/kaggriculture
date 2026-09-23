from kaggle_environments import make
from farmer3 import my_agent
import argparse
import json

parser = argparse.ArgumentParser()

parser.add_argument('-s', '--seed')      # option that takes a value
parser.add_argument('-t', '--turns')      # option that takes a value
parser.add_argument('-d', '--debug',
                    action='store_true')  # on/off flag
parser.add_argument('-j', '--json',
                    action='store_true')  # on/off flag


args = parser.parse_args()

configuration = {"episodeSteps": 720}

if args.seed:
    configuration["seed"] = int(args.seed)

if args.turns:
    configuration["episodeSteps"] = int(args.turns)

env = make("kaggriculture", configuration, debug=args.debug)
env.run([my_agent, "pass"])

html = env.render(mode="html", width=1200, height=800)
with open("replay.html", "w") as f:
    f.write(html)

if args.json:
    with open("replay.json", "w") as f:
        json.dump(env.toJSON(), f)

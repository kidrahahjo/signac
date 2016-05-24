import json
import signac

with open('index.txt') as file:
    for line in file:
        doc = json.loads(line)
        file = signac.fetch_one(doc)
        V = float(file.read())
        print(doc['statepoint'], V)

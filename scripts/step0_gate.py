import sys, collections
sys.path.insert(0, "src")  # run from repo root
from ctgov import fetch_page
rows = {}
for st in ("COMPLETED", "TERMINATED"):
    d = fetch_page(st, 1000)
    print(st, "totalCount:", d.get("totalCount"), "first page:", len(d["studies"]), "nextPageToken:", bool(d.get("nextPageToken")))
    rows[st] = d["studies"]
allst = rows["COMPLETED"] + rows["TERMINATED"]
print("fetched:", len(allst))
s = allst[0]["protocolSection"]
print("modules:", list(s))
for m in ("designModule", "eligibilityModule", "outcomesModule", "sponsorCollaboratorsModule", "statusModule", "armsInterventionsModule", "oversightModule", "conditionsModule"):
    print(" ", m, list(s.get(m, {})))
t = rows["TERMINATED"]
print("whyStopped present in terminated page:", sum('whyStopped' in x["protocolSection"]["statusModule"] for x in t), "/", len(t))
import random; random.seed(0)
w = [x["protocolSection"]["statusModule"].get("whyStopped") for x in t]
w = [x for x in w if x]
for x in random.sample(w, 5): print("  -", x[:160])

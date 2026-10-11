import sys, json
sys.path.insert(0, "src")
from ctgov import fetch_all
s = fetch_all()
print("TOTAL", len(s), "unique", len({x["protocolSection"]["identificationModule"]["nctId"] for x in s}))

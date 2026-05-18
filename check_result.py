import httpx
import json
import sys
import os

os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("ALL_PROXY", None)

task_id = sys.argv[1] if len(sys.argv) > 1 else "95f97488-d4d0-4ac3-b45a-fcacf2c6995c"
r = httpx.get(f"http://localhost:8000/api/v1/review/{task_id}", timeout=30)
d = r.json()
print(f"status: {d.get('status')}")
print(f"risk: {d.get('overall_risk')}")
print(f"level: {d.get('risk_level')}")
dims = d.get("dimensions", [])
print(f"dims: {len(dims)}")
for x in dims:
    print(f"  {x['name']}: {x['score']} ({x['severity']})")
reactions = d.get("platform_reactions", {})
print(f"platforms: {list(reactions.keys())}")

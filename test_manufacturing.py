"""Quick test: run a manufacturing analysis."""
import json, urllib.request

data = json.dumps({"blueprint_type_id": 32773, "region_id": 10000002}).encode()
req = urllib.request.Request(
    "http://localhost:8000/api/v1/manufacturing/analyze",
    data=data,
    headers={"Content-Type": "application/json"}
)
resp = urllib.request.urlopen(req)
print(resp.read().decode()[:800])

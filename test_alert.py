import json, urllib.request

# Create alert
data = json.dumps({"type_id": 34, "region_id": 10000002, "condition": "below", "threshold": 5.0}).encode()
req = urllib.request.Request("http://localhost:8000/api/v1/alerts/", data=data,
    headers={"Content-Type": "application/json"})
r = urllib.request.urlopen(req)
alert = json.loads(r.read())
print(f"Created: id={alert['id']} type_id={alert['type_id']} {alert['condition']} {alert['threshold']} ISK")

# List
req2 = urllib.request.Request("http://localhost:8000/api/v1/alerts/")
r2 = urllib.request.urlopen(req2)
alerts = json.loads(r2.read())
print(f"Total alerts: {len(alerts)}")

# Toggle (disable)
data3 = json.dumps({"is_active": False}).encode()
req3 = urllib.request.Request(f"http://localhost:8000/api/v1/alerts/{alert['id']}",
    data=data3, headers={"Content-Type": "application/json"}, method="PUT")
r3 = urllib.request.urlopen(req3)
updated = json.loads(r3.read())
print(f"Toggled: active={updated['is_active']}")

# Delete
req4 = urllib.request.Request(f"http://localhost:8000/api/v1/alerts/{alert['id']}", method="DELETE")
r4 = urllib.request.urlopen(req4)
print(f"Deleted: {json.loads(r4.read())['message']}")

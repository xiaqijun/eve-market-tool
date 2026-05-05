import json, urllib.request

# Create a trade
data = json.dumps({
    "type_id": 34,
    "region_id": 10000002,
    "station_id": 60003760,
    "buy_price": 3.5,
    "sell_price": 4.2,
    "quantity": 1000000,
    "notes": "test"
}).encode()

req = urllib.request.Request(
    "http://localhost:8000/api/v1/trading/trades",
    data=data, headers={"Content-Type": "application/json"}
)
resp = urllib.request.urlopen(req)
trade = json.loads(resp.read())
print(f"Created trade id={trade['id']}")

# Complete it
data2 = json.dumps({
    "status": "completed",
    "net_profit": 700000,
    "profit_margin": 0.2
}).encode()
req2 = urllib.request.Request(
    f"http://localhost:8000/api/v1/trading/trades/{trade['id']}",
    data=data2, headers={"Content-Type": "application/json"}, method="PUT"
)
resp2 = urllib.request.urlopen(req2)
updated = json.loads(resp2.read())
print(f"Completed: profit={updated['net_profit']} margin={updated['profit_margin']}")

# Summary
req3 = urllib.request.Request("http://localhost:8000/api/v1/trading/summary")
resp3 = urllib.request.urlopen(req3)
s = json.loads(resp3.read())
print(f"Summary: {s['total_trades']} trades | active={s['active_trades']} completed={s['completed_trades']} profit={s['total_profit']}")

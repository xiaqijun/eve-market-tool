"""Explore SDE SQLite schema — find blueprint/industry tables."""
import sqlite3, os, sys

# Find SDE file
sde_path = None
for f in os.listdir("."):
    if "sde" in f.lower() and f.endswith(".sqlite"):
        sde_path = f
        break

if not sde_path:
    print("No SDE SQLite found")
    sys.exit(1)

sde = sqlite3.connect(sde_path)

# List industry-related tables
print("=== Industry/Blueprint tables ===")
tables = [r[0] for r in sde.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND (name LIKE '%industry%' OR name LIKE '%blueprint%')
""").fetchall()]
for t in tables:
    print(f"\n{t}")
    cols = sde.execute(f"PRAGMA table_info({t})").fetchall()
    for c in cols:
        print(f"  {c[1]} ({c[2]})")
    # Show row count
    count = sde.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  => {count} rows")

# Sample data from key tables
for t in tables:
    print(f"\n=== Sample from {t} ===")
    rows = sde.execute(f"SELECT * FROM {t} LIMIT 3").fetchall()
    for r in rows:
        print(r)

sde.close()

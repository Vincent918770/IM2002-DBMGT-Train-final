import json
import random
from datetime import datetime, timedelta, timezone

def random_date(start, end):
    delta = end - start
    random_days = random.randrange(delta.days)
    random_seconds = random.randrange(24*60*60)
    return start + timedelta(days=random_days, seconds=random_seconds)

start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
end_date = datetime(2025, 6, 1, tzinfo=timezone.utc)

# Generate lost_items
lost_items = []
categories = ["Electronics", "Clothing", "Baggage", "Accessories", "Documents"]
stations = ["MS01", "MS02", "MS03", "NR01", "NR02"]
statuses = ["reported", "found", "claimed"]

for i in range(1, 41):
    status = random.choice(statuses)
    found_date = random_date(start_date, end_date)
    item = {
        "item_id": f"LI-{i:03d}",
        "found_date": found_date.isoformat() if status != "reported" else None,
        "reported_date": (found_date - timedelta(days=1)).isoformat(),
        "station_id": random.choice(stations),
        "category": random.choice(categories),
        "description": f"A lost {random.choice(categories).lower()} item",
        "is_high_value": random.choice([True, False]),
        "has_personal_info": random.choice([True, False]),
        "status": status,
        "claimed_by_user": f"RU{random.randint(1,10):02d}" if status == "claimed" else None,
        "claimed_date": (found_date + timedelta(days=random.randint(1, 10))).isoformat() if status == "claimed" else None
    }
    lost_items.append(item)

with open('train-mock-data/lost_items.json', 'w', encoding='utf-8') as f:
    json.dump(lost_items, f, indent=2)

# Generate penalties
penalties = []
violation_types = ["fare_evasion", "smoking", "prohibited_items"]

for i in range(1, 41):
    status = random.choice(["unpaid", "paid", "appealed"])
    violation_date = random_date(start_date, end_date)
    penalty = {
        "penalty_id": f"PN-{i:03d}",
        "user_id": f"RU{random.randint(1,10):02d}",
        "violation_type": random.choice(violation_types),
        "violation_date": violation_date.isoformat(),
        "location": random.choice(stations),
        "amount_usd": round(random.uniform(50.0, 150.0), 2),
        "status": status,
        "due_date": (violation_date + timedelta(days=30)).isoformat(),
        "paid_at": (violation_date + timedelta(days=random.randint(1, 20))).isoformat() if status == "paid" else None
    }
    penalties.append(penalty)

with open('train-mock-data/penalties.json', 'w', encoding='utf-8') as f:
    json.dump(penalties, f, indent=2)

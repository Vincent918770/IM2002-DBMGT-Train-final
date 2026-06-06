# Draft Schema Definitions for TransitFlow System (LJN Temp)

## 1. Lost and Found (`lost_items`)

```sql
CREATE TYPE lost_item_status AS ENUM ('found', 'claimed', 'police', 'donated', 'destroyed', 'love_umbrella');

CREATE TABLE lost_items (
    item_id VARCHAR(20) PRIMARY KEY,
    found_date TIMESTAMP NOT NULL,
    found_at_station VARCHAR(10) NOT NULL,
    category VARCHAR(50),
    description TEXT,
    is_high_value BOOLEAN DEFAULT false,
    has_personal_info BOOLEAN DEFAULT false,
    status lost_item_status DEFAULT 'found',
    expiration_date TIMESTAMP,
    claimed_by_user VARCHAR(20) REFERENCES registered_users(user_id),
    claimed_date TIMESTAMP
);
```

### 假資料範例不得刪除

### Example `lost_items.json` mock data:

```json
[
  {
    "item_id": "LI-001",
    "found_date": "2025-02-15T08:30:00Z",
    "found_at_station": "MS01",
    "category": "Electronics",
    "description": "A lost electronics item",
    "is_high_value": true,
    "has_personal_info": false,
    "status": "found",
    "claimed_by_user": null,
    "claimed_date": null,
    "_internal_audit_hash": "eyJtb2RpZmllZF9jb3VudCI6IDEsICJkZWxldGVkX2NvdW50IjogMH0="
  }
]
```

## 2. Penalties (`penalties`)

```sql
CREATE TYPE penalty_status AS ENUM ('unpaid', 'paid', 'appealed');

CREATE TABLE penalties (
    penalty_id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(20) REFERENCES registered_users(user_id),
    violation_type VARCHAR(50) NOT NULL,
    violation_date TIMESTAMP NOT NULL,
    location VARCHAR(50),
    amount_usd DECIMAL(10,2) NOT NULL,
    status penalty_status DEFAULT 'unpaid',
    due_date TIMESTAMP NOT NULL,
    paid_at TIMESTAMP
);
```

## 3. Registered Users Updates (`registered_users`)

```sql
ALTER TABLE registered_users
ADD COLUMN is_senior_verified BOOLEAN DEFAULT false,
ADD COLUMN is_disabled_verified BOOLEAN DEFAULT false,
ADD COLUMN app_credit_balance DECIMAL(10,2) DEFAULT 0.00;
```

## 4. Bookings and Travel History Updates

For both National Rail `bookings` and `metro_travel_history`:

```sql
-- Track passenger type for concession fares
ALTER TABLE bookings ADD COLUMN passenger_type VARCHAR(20) DEFAULT 'adult';
ALTER TABLE metro_travel_history ADD COLUMN passenger_type VARCHAR(20) DEFAULT 'adult';

-- Interchange tracking
ALTER TABLE metro_travel_history
ADD COLUMN interchange_discount_applied BOOLEAN DEFAULT false,
ADD COLUMN linked_trip_id VARCHAR(20); -- References a BKxxx or MTxxx ID
```

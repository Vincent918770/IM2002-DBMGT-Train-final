# AI Session Context — TransitFlow

**How to use this file:**
At the start of every AI coding session, paste the full contents of this file as your first message to your AI assistant. This gives the AI the context it needs to produce code that fits your codebase and is consistent with your teammates' work.

**Who maintains this file:**
Whoever makes a schema change or architectural decision updates this file in the same commit. Treat it like a team contract.

---

## Project Overview

TransitFlow is a Python-based AI chat assistant for a fictional transit operator. It queries three databases — PostgreSQL (relational + vector), Neo4j (graph) — and uses an LLM to answer user questions. Our task as students is to design the database schema and implement the query functions in `databases/relational/queries.py` and `databases/graph/queries.py`.

## Tech Stack

- Language: Python 3.11+
- Relational DB: PostgreSQL via `psycopg2` with `RealDictCursor`
- Graph DB: Neo4j via the `neo4j` Python driver
- Vector search: `pgvector` extension (already implemented — do not modify)
- Web UI: Gradio
- LLM: Google Gemini or local Ollama (configured via `.env`)

## Coding Conventions

- **Naming:** `snake_case` for all Python names and SQL identifiers
- **Docstrings:** All functions must have a docstring with `Args:` and `Returns:` sections
- **Return types:** Use type hints. Read-only functions return `list[dict]` or `Optional[dict]`
- **Empty results:** Return `[]` or `None` (as documented), never raise an exception for "not found"
- **SQL:** Use `%s` placeholders for all user inputs — never string-format into SQL
- **Relational pattern:** Use `_connect()` helper + `psycopg2.extras.RealDictCursor`:
  ```python
  with _connect() as conn:
      with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
          cur.execute("SELECT ...", (param,))
          return [dict(row) for row in cur.fetchall()]
  ```
- **Graph pattern:** Use `_driver()` helper + session:
  ```python
  with _driver() as driver:
      with driver.session() as session:
          result = session.run("MATCH ...", station_id=station_id)
          return [dict(record) for record in result]
  ```

## Agreed Relational Schema

<!-- ============================================================
  FILL THIS IN after your team completes the schema design workshop.
  Paste your final CREATE TABLE statements here.
  ============================================================ -->

```sql
-- TODO: paste your final schema.sql contents here after team review
```
### 第一層：獨立基礎層 (沒有外鍵，最先畫)

#### 1. Users (使用者)
- `user_id` (PK, VARCHAR) - 主鍵
- `email` (VARCHAR, UNIQUE, NOT NULL)
- `password_hash` (VARCHAR, NOT NULL)
- `first_name` (VARCHAR, NOT NULL)
- `surname` (VARCHAR, NOT NULL)
- `year_of_birth` (INT, NOT NULL) - [限制：需大於 1900]
- `membership_level` (VARCHAR) - (我們新增的亮點)
- `loyalty_points` (INT) - (我們新增的亮點)

#### 2. Stations (車站)
- `station_id` (PK, VARCHAR) - 主鍵
- `station_name` (VARCHAR, NOT NULL)
- `network_type` (VARCHAR, NOT NULL) - [限制：只能是 'metro' 或 'national_rail'，我們新增的區分欄位]

---

### 第二層：核心設施層 (依賴基礎層)

#### 3. Schedules (車次班表)
- `schedule_id` (PK, VARCHAR) - 主鍵
- `origin_station_id` (FK, VARCHAR, NOT NULL) - 連向 Stations
- `destination_station_id` (FK, VARCHAR, NOT NULL) - 連向 Stations
- `departure_time` (TIME, NOT NULL)
- `arrival_time` (TIME, NOT NULL)
- `delay_minutes` (INT) - (我們新增的亮點)
- `status` (VARCHAR) - (我們新增的亮點)

#### 4. Seat Layouts (國鐵座位配置)
- `layout_id` (PK, VARCHAR) - 主鍵 (或是用複合主鍵)
- `schedule_id` (FK, VARCHAR, NOT NULL) - 連向 Schedules
- `coach` (VARCHAR, NOT NULL)
- `seat_id` (VARCHAR, NOT NULL)
- `fare_class` (VARCHAR, NOT NULL)

---

### 第三層：業務交易層 (依賴前兩層)

#### 5. Bookings (國鐵預約訂單)
- `booking_id` (PK, VARCHAR) - 主鍵
- `user_id` (FK, VARCHAR, NOT NULL) - 連向 Users
- `schedule_id` (FK, VARCHAR, NOT NULL) - 連向 Schedules
- `origin_station_id` (FK, VARCHAR, NOT NULL) - 連向 Stations
- `destination_station_id` (FK, VARCHAR, NOT NULL) - 連向 Stations
- `travel_date` (DATE, NOT NULL)
- `ticket_type` (VARCHAR, NOT NULL)
- `fare_class` (VARCHAR, NOT NULL)
- `coach` (VARCHAR)
- `seat_id` (VARCHAR)
- `stops_travelled` (INT, NOT NULL)
- `amount_usd` (DECIMAL, NOT NULL)
- `status` (VARCHAR, NOT NULL)
- `booked_at` (TIMESTAMPTZ, NOT NULL)
- `travelled_at` (TIMESTAMPTZ) - [可為空 (NULL)，因為還沒搭車]

#### 6. Trips (捷運乘車紀錄)
- `trip_id` (PK, VARCHAR) - 主鍵
- `user_id` (FK, VARCHAR, NOT NULL) - 連向 Users
- `tap_in_station_id` (FK, VARCHAR, NOT NULL) - 連向 Stations
- `tap_out_station_id` (FK, VARCHAR) - 連向 Stations [進站時還沒有出站紀錄，所以可為空]
- `tap_in_time` (TIMESTAMPTZ, NOT NULL)
- `tap_out_time` (TIMESTAMPTZ)
- `fare_usd` (DECIMAL)

---

### 第四層：後續互動層 (收尾)

#### 7. Payments (付款紀錄)
- `payment_id` (PK, VARCHAR) - 主鍵
- `booking_id` (FK, VARCHAR) - 連向 Bookings [如果是國鐵訂單就有值]
- `trip_id` (FK, VARCHAR) - 連向 Trips [如果是捷運搭乘就有值]
- `amount` (DECIMAL, NOT NULL)
- `payment_method` (VARCHAR, NOT NULL)
- `payment_status` (VARCHAR, NOT NULL)
- `paid_at` (TIMESTAMPTZ, NOT NULL)

#### 8. Feedback (意見回饋)
- `feedback_id` (PK, VARCHAR) - 主鍵
- `user_id` (FK, VARCHAR, NOT NULL) - 連向 Users
- `booking_id` (FK, VARCHAR) - 連向 Bookings (選填，看是對哪筆訂單留評價)
- `trip_id` (FK, VARCHAR) - 連向 Trips (選填，看是對哪趟捷運留評價)
- `rating` (INT, NOT NULL) - [限制：1 到 5 分]
- `comments` (TEXT)
- `submitted_at` (TIMESTAMPTZ, NOT NULL)

## Agreed Graph Schema

<!-- ============================================================
  FILL THIS IN after your team agrees on Neo4j node labels and
  relationship types.
  ============================================================ -->

```
Node labels:
- TODO

Relationship types:
- TODO

Key properties:
- TODO
```

## Function Signatures We Are Implementing

These are fixed contracts. AI-generated code must match these signatures exactly.

### Relational (`databases/relational/queries.py`)

```python
# Read-only
def query_national_rail_availability(origin_id: str, destination_id: str, travel_date: Optional[str] = None) -> list[dict]: ...
def query_national_rail_fare(schedule_id: str, fare_class: str, stops_travelled: int) -> Optional[dict]: ...
def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]: ...
def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]: ...
def query_available_seats(schedule_id: str, travel_date: str, fare_class: str) -> list[dict]: ...
def query_user_profile(user_email: str) -> Optional[dict]: ...
def query_user_bookings(user_email: str) -> dict: ...  # returns {"national_rail": [...], "metro": [...]}
def query_payment_info(booking_id: str) -> Optional[dict]: ...

# Write operations
def execute_booking(user_id, schedule_id, origin_station_id, destination_station_id, travel_date, fare_class, seat_id, ticket_type="single") -> tuple[bool, dict | str]: ...
def execute_cancellation(booking_id: str, user_id: str) -> tuple[bool, dict | str]: ...

# Auth
def register_user(email, first_name, surname, year_of_birth, password, secret_question, secret_answer) -> tuple[bool, str]: ...
def login_user(email: str, password: str) -> Optional[dict]: ...
def get_user_secret_question(email: str) -> Optional[str]: ...
def verify_secret_answer(email: str, answer: str) -> bool: ...
def update_password(email: str, new_password: str) -> bool: ...
```

### Graph (`databases/graph/queries.py`)

```python
def query_shortest_route(origin_id: str, destination_id: str, network: str = "auto") -> dict: ...
def query_cheapest_route(origin_id: str, destination_id: str, network: str = "auto", fare_class: str = "standard") -> dict: ...
def query_alternative_routes(origin_id, destination_id, avoid_station_id, network="auto", max_routes=3) -> list[list[dict]]: ...
def query_interchange_path(origin_id: str, destination_id: str) -> dict: ...
def query_delay_ripple(delayed_station_id: str, hops: int = 2) -> list[dict]: ...
def query_station_connections(station_id: str) -> list[dict]: ...
```

## Team Decisions Log

<!-- Add entries as you make decisions. Format: "Decision: X. Why: Y." -->

- [ ] Schema design: TODO — add your table/column decisions here
- [ ] Graph schema: TODO — add your node label and relationship type decisions here
- [ ] (example) Metro schedule stop ordering: using `jsonb_array_elements` approach — easier to debug than containment operators

## Prompts That Worked

<!-- Share prompts that produced good output so teammates can reuse them. -->

### Schema design prompt that worked:
```
TODO — add a prompt here after your schema design workshop
```

### Query implementation prompt that worked:
```
TODO — add after implementing your first function
```

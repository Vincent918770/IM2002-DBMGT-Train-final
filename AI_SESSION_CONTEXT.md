# AI Session Context — TransitFlow

[Jump to Team Decisions Log](#team-decisions-log)
**How to use this file:**

**CRITICAL INSTRUCTION FOR AI:**
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

`sql
-- ============================================================
-- TransitFlow PostgreSQL Schema

## -- Seed data is loaded separately by: python skeleton/seed_postgres.py

-- TWO ROLES:
-- 1. Relational -> dual-network transit data you design below
-- 2. Vector -> policy documents for RAG (provided -- do not modify)
-- ============================================================

-- ============================================================
-- STUDENT TASK -- Design and create your relational tables here
--
-- _Verification Note_: The "Architect Note: Concept Origination & Refinement"
-- comment has been successfully verified to exist in databases/relational/schema.sql,
-- skeleton/seed_postgres.py, and databases/relational/queries.py,
-- confirming 10LJN09's original conceptualization and refinement.
--
-- Start from the mock data in train-mock-data/:
-- metro_stations.json, national_rail_stations.json
-- metro_schedules.json, national_rail_schedules.json
-- national_rail_seat_layouts.json
-- registered_users.json
-- bookings.json, metro_travel_history.json
-- payments.json, feedback.json
--
-- Think about:
-- - What tables do you need?
-- - What columns and data types?
-- - Which fields are primary keys? Which are foreign keys?
-- - What constraints make sense?
--
-- Apply your schema with:
-- docker-compose down -v && docker-compose up -d
-- ============================================================

-- ============================================================
-- MANDATORY DESIGN COMMENTS (Rubric Requirements)
--
-- [1] PK Design Choice (VARCHAR vs SERIAL/UUID):
-- We explicitly chose VARCHAR for core business primary keys (user_id, booking_id)
-- instead of database-native SERIAL or UUID. In a transit system, IDs must be highly
-- readable for frontline customer service (e.g., 'BK' for Booking, 'LI' for Lost Item).
-- Furthermore, prefixed VARCHARs enable polymorphic routing (see point 5).
-- SERIAL is strictly reserved for internal, non-business identifiers (e.g., coach_id).
--
-- [2] Delete Strategy (Soft vs Hard):
-- SOFT DELETE is used for the `users` table via the `is_active` BOOLEAN flag.
-- This preserves the integrity of all historical transaction records
-- (bookings, penalties, payments). Conversely, credentials in `users_confidential` are
-- HARD DELETED via ON DELETE CASCADE for strict security and data minimization.
--
-- [3] FK Cascade Behaviors:
-- - `users_confidential` -> `users`: ON DELETE CASCADE
-- Credentials must be immediately destroyed if the parent user is purged.
-- - All other Foreign Keys use the default ON DELETE RESTRICT behavior.
-- This prevents accidental deletion of parent records that still have
-- associated transaction history (bookings, penalties, travel history).
--
-- [4] Password Security:
-- Passwords stored in `users_confidential.password` are securely hashed using the
-- adaptive Argon2id algorithm via the application layer (skeleton/seed_postgres.py).
-- Plain-text passwords and weak hashes (MD5/SHA-1) are strictly prohibited.
--
-- [5] Polymorphic Associations (Trade-off):
-- The `linked_trip_id` column tracks cross-network transfers (Metro to Rail) without
-- strict SQL Foreign Keys. We traded strict database-level referential integrity for
-- architectural decoupling. The Python application layer reads the VARCHAR prefix
-- ('BK' vs 'MT') to dynamically route queries. This prevents combinatorial explosion
-- of FK columns and prepares the schema for microservice separation.
--
-- [6] Defensive Constraints & State Machines:
-- We heavily utilized CHECK constraints (e.g., passenger_type) and ENUM types
-- (e.g., lost_item_status, concession_verification_status). This defensive design
-- pushes real-world operational state machines directly into the schema layer,
-- rejecting dirty data (like typos or invalid states) before it can corrupt the database.
-- ============================================================

-- =========================================================================
-- [ Architect Note: Concept Origination & Refinement ]
-- While the general schema integration was handled by Vic,and initial table structures were generated by whole group,
-- the foundational architecture below (including the separation of users_confidential, part of core
-- table relationships, etc.) was originally conceptualized
-- by Lucas (10LJN09) in the feat/schema-ex branch, and extensively adjusted
-- and verified by Lucas in this final version.
-- =========================================================================

-- =========================================================================
-- [ Users & Confidential Information Design ]
-- Description: Extracted sensitive data into `users_confidential` for best practice
-- data separation following the principle of least privilege.
-- Security: Only admin-level DB roles have access to users_confidential.
-- This minimizes the blast radius in the event of a data breach.
-- Relationship: Strict 1-to-1 binding using `user_id` as PK & FK.
-- Note for Seed Script: Must insert into both tables simultaneously with matching user_id.
-- =========================================================================

-- Q: How to handle user account deletion?
-- A: Use is_active for soft deletion to retain transaction history.
-- Q: Should users_confidential be soft-deleted or hard-deleted?
-- A: Hard-deleted via CASCADE to destroy credentials immediately upon admin removal.
CREATE TABLE IF NOT EXISTS users (
user_id VARCHAR(50) PRIMARY KEY,
-- PK: VARCHAR prefix-based ID (e.g., 'U001') generated by application layer.
full_name VARCHAR(100) NOT NULL,
email VARCHAR(255) UNIQUE NOT NULL,
phone VARCHAR(20),
date_of_birth DATE,
registered_at TIMESTAMPTZ,
-- TIMESTAMPTZ: stores timezone-aware timestamp for global correctness.
is_active BOOLEAN DEFAULT true,
-- Soft delete flag. Set to false instead of hard-deleting to preserve history.
-- =========================================================================
-- [ LJN - Users Verified Concession ]
-- Description: Added verified_concession instead of a simple is_verified boolean.
-- Reason: A boolean cannot differentiate between 'senior' and 'disabled' concessions.
-- Note: CHECK constraints implicitly allow NULLs, so unverified/general adults remain NULL.
-- =========================================================================
verified_concession VARCHAR(20) CHECK (verified_concession IN ('senior', 'disabled')),
app_credit_balance NUMERIC(10,2) DEFAULT 0.00
-- NUMERIC(10,2): mandatory for monetary values per rubric. Do NOT use FLOAT or TEXT.
);

-- =========================================================================
-- Extracted sensitive info into a separate table.
-- FK Cascade: ON DELETE CASCADE -> credentials are destroyed if user is hard-deleted.
-- Security: Passwords are hashed using Argon2id via the application layer.
-- See skeleton/seed_postgres.py for implementation.
-- =========================================================================
CREATE TABLE IF NOT EXISTS users_confidential (
user_id VARCHAR(50) PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
-- ON DELETE CASCADE: explicitly declared per rubric requirement.
password VARCHAR(255) NOT NULL,
-- Stores Argon2id hash string (e.g., "$argon2id$v=19$..."). Never plain-text.
secret_question VARCHAR(255),
secret_answer VARCHAR(255)
);

-- =========================================================================
-- [ Interchange Lines Column Removal & Architecture Update ]
-- Description: Removed `interchange_lines` array columns to prevent 1NF violation
-- and data redundancy.
-- Reason: Overlaps with `lines`; complex graph queries are better handled by Neo4j.
-- Alternative: PostgreSQL retains lightweight `is_interchange_xxx` booleans for
-- fast UI queries; detailed route topology is delegated to Neo4j.
-- Note for Seed Script: Ignore JSON line arrays. Only insert true/false boolean flags.
-- =========================================================================
-- [ Adjacent Stations Data Removal & Architecture Update ]
-- Description: Excluded `adjacent_stations` object arrays from PostgreSQL to prevent
-- 1NF violation.
-- Strategy: Polyglot persistence. PostgreSQL handles core transactions;
-- Neo4j handles network topology.
-- Note for Neo4j Team: Parse `adjacent_stations` from JSON into Graph Relationships.
-- =========================================================================
CREATE TABLE IF NOT EXISTS metro_stations (
station_id VARCHAR(10) PRIMARY KEY,
-- PK: VARCHAR business key matching source JSON identifiers.
name VARCHAR(100) NOT NULL,
is_interchange_metro BOOLEAN,
is_interchange_national_rail BOOLEAN,
interchange_national_rail_station_id VARCHAR(10),
lines TEXT[]
-- TEXT[]: array of line codes (e.g., '{Red, Blue}'). Kept for lightweight UI display.
-- Detailed topology is stored in Neo4j, not here.
);

-- =========================================================================
-- [ Interchange Lines & Adjacent Stations: same rationale as metro_stations above ]
-- =========================================================================
CREATE TABLE IF NOT EXISTS national_rail_stations (
station_id VARCHAR(10) PRIMARY KEY,
-- PK: VARCHAR business key matching source JSON identifiers.
name VARCHAR(100) NOT NULL,
is_interchange_national_rail BOOLEAN,
is_interchange_metro BOOLEAN,
interchange_metro_station_id VARCHAR(10),
lines TEXT[]
);

-- =========================================================================
-- [ Schedule Stops & Travel Time Architecture Update ]
-- Description: Extracted stops arrays into `metro_schedule_stops` detail table
-- to comply with 1NF. Arrays in parent tables would violate atomicity.
-- Advantages: Replaces slow array parsing with fast precise queries;
-- enables FK data integrity enforcement.
-- Renaming: `stops_in_order` renamed to singular `stop_order` for per-row clarity.
-- Note for Seed Script: Two-step insertion. Insert main table first, then loop
-- the array to insert detail rows.
-- =========================================================================
CREATE TABLE IF NOT EXISTS metro_schedules (
schedule_id VARCHAR(20) PRIMARY KEY,
-- PK: VARCHAR business key matching source JSON identifiers.
line VARCHAR(10),
direction VARCHAR(20),
origin_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
-- FK: ON DELETE RESTRICT (default) -- prevents deleting a station that has schedules.
destination_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
first_train_time TIME,
last_train_time TIME,
base_fare_usd NUMERIC(5,2),
-- NUMERIC: mandatory for monetary values per rubric.
per_stop_rate_usd NUMERIC(5,2),
frequency_min INT,
operates_on TEXT[]
);

-- Junction table: enforces 1NF by replacing the stops array with individual rows.
-- Composite PK (schedule_id, station_id) ensures no duplicate stop per schedule.
CREATE TABLE IF NOT EXISTS metro_schedule_stops (
schedule_id VARCHAR(20) REFERENCES metro_schedules(schedule_id),
-- FK: ON DELETE RESTRICT (default).
station_id VARCHAR(10) REFERENCES metro_stations(station_id),
stop_order INT NOT NULL,
-- stop_order: mandatory per rubric (schedule stops must have a stop_order column).
travel_time_from_origin_min INT,
PRIMARY KEY (schedule_id, station_id)
-- Composite PK: uniquely identifies each stop within a schedule.
);

-- =========================================================================
-- [ Fare Classes Architecture Update ]
-- Description: Extracted `fare_classes` into a separate `national_rail_fares` table.
-- Purpose: Avoids hardcoded columns; scalable when new fare classes are added
-- without schema migration. Improves query efficiency.
-- Note for Seed Script: Two-step insertion. Insert main table first, then parse
-- the fare_classes dictionary into detail rows.
-- =========================================================================
CREATE TABLE IF NOT EXISTS national_rail_schedules (
schedule_id VARCHAR(20) PRIMARY KEY,
-- PK: VARCHAR business key matching source JSON identifiers.
line VARCHAR(10),
service_type VARCHAR(20),
direction VARCHAR(20),
origin_station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
-- FK: ON DELETE RESTRICT (default).
destination_station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
first_train_time TIME,
last_train_time TIME,
frequency_min INT,
operates_on TEXT[]
);

-- =========================================================================
-- [ Passed Through Stations Architecture Update ]
-- Description: Added `is_passed_through` flag to unify stopping and express-pass
-- stations in a single table (single source of truth).
-- Purpose: Tracks occupied rail segments even for non-stopping trains,
-- enabling operational dispatch and scheduling queries.
-- Note for Seed Script: stopping stations = false, passed-through = true.
-- =========================================================================
CREATE TABLE IF NOT EXISTS national_rail_schedule_stops (
schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
-- FK: ON DELETE RESTRICT (default).
station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
stop_order INT NOT NULL,
-- stop_order: mandatory per rubric.
travel_time_from_origin_min INT,
is_passed_through BOOLEAN DEFAULT false,
PRIMARY KEY (schedule_id, station_id)
-- Composite PK: uniquely identifies each stop within a schedule.
);

-- =========================================================================
-- [ Fare Rates Normalization ]
-- Description: Extracted base fare and per-stop rates into independent NUMERIC columns.
-- Purpose: Ensures atomicity; allows direct mathematical fare calculations in SQL.
-- Note for Seed Script: Parse the corresponding JSON numbers into these two columns.
-- =========================================================================
CREATE TABLE IF NOT EXISTS national_rail_fares (
schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
-- FK: ON DELETE RESTRICT (default).
fare_class VARCHAR(20) CHECK (fare_class IN ('standard', 'first')),
base_fare_usd NUMERIC(5,2),
-- NUMERIC: mandatory for monetary values per rubric.
per_stop_rate_usd NUMERIC(5,2),
PRIMARY KEY (schedule_id, fare_class)
-- Composite PK: one fare entry per class per schedule.
);

CREATE TABLE IF NOT EXISTS national_rail_seat_layouts (
layout_id VARCHAR(20) PRIMARY KEY,
-- PK: VARCHAR business key.
schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id)
-- FK: ON DELETE RESTRICT (default).
);

-- Q: Why doesn't national_rail_coaches need schedule_id?
-- A: layout_id already implies schedule_id via the seat_layouts table. No redundancy needed.
-- Note: coach = coach code, fare_class = fare tier, layout_id = unique seat layout ID.
CREATE TABLE IF NOT EXISTS national_rail_coaches (
coach_id SERIAL PRIMARY KEY,
-- PK: SERIAL (auto-increment integer) -- no business-readable identifier needed here.
layout_id VARCHAR(20) REFERENCES national_rail_seat_layouts(layout_id),
-- FK: ON DELETE RESTRICT (default).
coach_name VARCHAR(5),
fare_class VARCHAR(20) CHECK (fare_class IN ('standard', 'first'))
);

-- Note: seat_id = seat label (e.g., '12A'), row_num = row number, column_letter = A/B/C/D.
CREATE TABLE IF NOT EXISTS national_rail_seats (
seat_id VARCHAR(10),
coach_id INT REFERENCES national_rail_coaches(coach_id),
-- FK: ON DELETE RESTRICT (default).
row_num INT,
column_letter VARCHAR(2),
PRIMARY KEY (seat_id, coach_id)
-- Composite PK: seat label is only unique within a coach.
);

-- =========================================================================
-- [ Ticket Type vs Passenger Type ]
-- Description: ticket_type (single/return) and passenger_type (adult/senior) are
-- deliberately separated to avoid a combinatorial explosion
-- (e.g., 'single_adult', 'return_senior', 'single_disabled' ...).
-- Snapshot rationale: passenger_type is recorded on the booking (not just on the
-- user profile) to preserve the transaction snapshot. An adult user
-- can legally purchase a senior ticket for a family member.
-- =========================================================================
-- [ Interchange Tracking ]
-- Description: interchange_discount_applied flags whether a cross-network discount
-- was applied. linked_trip_id uses a Polymorphic Association pattern --
-- no SQL FK is declared because it may reference either a 'BKxxx'
-- (national rail) or 'MTxxx' (metro) record.
-- Application logic (Python) resolves the target table via ID prefix.
-- =========================================================================
-- [ Passenger Type CHECK & Gate Verification ]
-- Description: CHECK constraint on passenger_type prevents dirty string data.
-- concession_verification_status replaces a simple boolean to precisely
-- track manual gate verification workflow for concession tickets.
-- =========================================================================
CREATE TABLE IF NOT EXISTS national_rail_bookings (
booking_id VARCHAR(20) PRIMARY KEY,
-- PK: VARCHAR prefix-based ID (e.g., 'BK001') generated by application layer.
user_id VARCHAR(50) REFERENCES users(user_id),
-- FK: ON DELETE RESTRICT (default) -- booking history must be preserved.
schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
origin_station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
destination_station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
travel_date DATE,
departure_time TIME,
ticket_type VARCHAR(20) CHECK (ticket_type IN ('single', 'return', 'day_pass')),
passenger_type VARCHAR(20) DEFAULT 'adult' CHECK (passenger_type IN ('adult', 'senior', 'disabled')),
interchange_discount_applied BOOLEAN DEFAULT false,
linked_trip_id VARCHAR(20),
-- Polymorphic Association: no FK constraint. See note above.
fare_class VARCHAR(20) CHECK (fare_class IN ('standard', 'first')),
coach VARCHAR(5),
seat_id VARCHAR(10),
concession_verification_status VARCHAR(20) DEFAULT 'not_required'
CHECK (concession_verification_status IN ('not_required', 'pending_gate_check', 'verified_at_gate')),
stops_travelled INT,
amount_usd NUMERIC(8,2),
-- NUMERIC: mandatory for monetary values per rubric.
status VARCHAR(20) CHECK (status IN ('completed', 'confirmed', 'cancelled')),
booked_at TIMESTAMPTZ,
-- TIMESTAMPTZ: timezone-aware per rubric.
travelled_at TIMESTAMPTZ
);

-- Q: Added day_pass_ref -- it does exist in the source JSON.
-- Q: Will rides on different days share the same day_pass? No -- travel_date distinguishes them.
CREATE TABLE IF NOT EXISTS metro_travel_history (
trip_id VARCHAR(20) PRIMARY KEY,
-- PK: VARCHAR prefix-based ID (e.g., 'MT001') generated by application layer.
user_id VARCHAR(50) REFERENCES users(user_id),
-- FK: ON DELETE RESTRICT (default).
schedule_id VARCHAR(20) REFERENCES metro_schedules(schedule_id),
origin_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
destination_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
travel_date DATE,
ticket_type VARCHAR(20) CHECK (ticket_type IN ('single', 'return', 'day_pass')),
passenger_type VARCHAR(20) DEFAULT 'adult' CHECK (passenger_type IN ('adult', 'senior', 'disabled')),
day_pass_ref VARCHAR(20) REFERENCES metro_travel_history(trip_id),
-- Self-referencing FK for day pass grouping. ON DELETE RESTRICT (default).
interchange_discount_applied BOOLEAN DEFAULT false,
linked_trip_id VARCHAR(20),
-- Polymorphic Association: no FK constraint. Resolved by Python via ID prefix.
concession_verification_status VARCHAR(20) DEFAULT 'not_required'
CHECK (concession_verification_status IN ('not_required', 'pending_gate_check', 'verified_at_gate')),
stops_travelled INT,
amount_usd NUMERIC(8,2),
-- NUMERIC: mandatory for monetary values per rubric.
status VARCHAR(20) CHECK (status IN ('completed', 'confirmed', 'cancelled', 'active')),
purchased_at TIMESTAMPTZ,
-- TIMESTAMPTZ: timezone-aware per rubric.
travelled_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS payments (
payment_id VARCHAR(20) PRIMARY KEY,
-- PK: VARCHAR business key.
booking_id VARCHAR(20) REFERENCES national_rail_bookings(booking_id),
-- FK: ON DELETE RESTRICT (default) -- payment records must persist with bookings.
amount_usd NUMERIC(8,2),
-- NUMERIC: mandatory for monetary values per rubric.
method VARCHAR(20),
status VARCHAR(20),
paid_at TIMESTAMPTZ
-- TIMESTAMPTZ: timezone-aware per rubric.
);

CREATE TABLE IF NOT EXISTS feedback (
feedback_id VARCHAR(20) PRIMARY KEY,
-- PK: VARCHAR business key.
booking_id VARCHAR(20) REFERENCES national_rail_bookings(booking_id),
-- FK: ON DELETE RESTRICT (default).
user_id VARCHAR(50) REFERENCES users(user_id),
rating INT,
comment TEXT,
submitted_at TIMESTAMPTZ
-- TIMESTAMPTZ: timezone-aware per rubric.
);

-- ============================================================
-- LOST ITEMS & PENALTIES
-- ============================================================

-- =========================================================================
-- [ Lost Items Status & High Value ]
-- Description:
-- 1. Added 'reported' status: user has reported a loss, but item not yet found by staff.
-- 2. is_high_value (> 150 USD): operational boolean set manually by station staff.
-- Reason: Real lost items are hard to appraise precisely; a boolean flag is operationally
-- simpler and avoids dirty/arbitrary monetary data entry by non-finance staff.
-- PK: VARCHAR item_id generated by application layer.
-- FK cascade: ON DELETE RESTRICT (default) on claimed_by_user to preserve records.
-- =========================================================================
CREATE TYPE lost_item_status AS ENUM ('reported', 'found', 'claimed', 'police', 'donated', 'destroyed', 'love_umbrella');

CREATE TABLE IF NOT EXISTS lost_items (
item_id VARCHAR(20) PRIMARY KEY,
-- PK: VARCHAR business key (e.g., 'LI001').
found_date TIMESTAMPTZ,
-- TIMESTAMPTZ: nullable -- null when status is 'reported' and item not yet found.
reported_date TIMESTAMPTZ,
station_id VARCHAR(10) REFERENCES metro_stations(station_id),
-- FK: ON DELETE RESTRICT (default). References the station where item was lost/found.
category VARCHAR(50),
description TEXT,
is_high_value BOOLEAN DEFAULT false,
-- Set by staff (e.g., estimated > 150 USD). Boolean avoids unreliable manual appraisal.
has_personal_info BOOLEAN DEFAULT false,
status lost_item_status DEFAULT 'found',
expiration_date TIMESTAMPTZ,
claimed_by_user VARCHAR(50) REFERENCES users(user_id),
-- FK: ON DELETE RESTRICT (default).
claimed_date TIMESTAMPTZ
);

-- =========================================================================
-- [ Penalties ]
-- Description: Records fare evasion and other violations linked to registered users.
-- Tracks payment lifecycle from unpaid through to paid or appealed.
-- PK: VARCHAR penalty_id generated by application layer.
-- FK cascade: ON DELETE RESTRICT (default) on user_id -- penalty records must persist.
-- =========================================================================
CREATE TYPE penalty_status AS ENUM ('unpaid', 'paid', 'appealed');

CREATE TABLE IF NOT EXISTS penalties (
penalty_id VARCHAR(20) PRIMARY KEY,
-- PK: VARCHAR business key (e.g., 'PN001').
user_id VARCHAR(50) REFERENCES users(user_id),
-- FK: ON DELETE RESTRICT (default) -- penalty must not vanish if user is soft-deleted.
violation_type VARCHAR(50) NOT NULL,
violation_date TIMESTAMPTZ NOT NULL,
-- TIMESTAMPTZ: timezone-aware per rubric.
location VARCHAR(50),
amount_usd NUMERIC(10,2) NOT NULL,
-- NUMERIC: mandatory for monetary values per rubric.
status penalty_status DEFAULT 'unpaid',
due_date TIMESTAMPTZ NOT NULL,
paid_at TIMESTAMPTZ
);

-- ============================================================
-- VECTOR SCHEMA (RAG / Help Desk) -- do not modify
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_documents (
id SERIAL PRIMARY KEY,
title VARCHAR(200) NOT NULL,
category VARCHAR(50) NOT NULL, -- 'refund', 'booking', 'conduct'
content TEXT NOT NULL,
-- 768-dim -> Ollama nomic-embed-text (default)
-- 3072-dim -> Gemini gemini-embedding-001
-- If you switch LLM_PROVIDER to gemini, change to vector(3072) and reset the database.
embedding vector(768),
source_file VARCHAR(200),
created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS ON policy_documents USING hnsw (embedding vector_cosine_ops);

`

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
- **Policy Documents Table**: Added `policy_documents` table to store and retrieve policy documents.
- **Penalty Fares & Lost Items Schemas**: Added `lost_items` and `penalties` schemas (drafted in `schema_LJN_temp.md`) to track specific statuses, deadlines, and violations. Why: Needed for relational state tracking beyond just RAG text lookup.
- **Concession Fares & App Credit**: Added `is_senior_verified`, `is_disabled_verified`, and `app_credit_balance` to `users` (previously `registered_users`). Why: To support senior/disabled tickets and wallet deductions.
- **Interchange Discount Logic (Polymorphic Association)**: Added `interchange_discount_applied` and `linked_trip_id` to booking tables instead of using rigid SQL foreign keys. Why: Allows backend Python routing based on ID prefix (e.g. `BK` for rail, `MT` for metro).
- **Passenger Type Constraints**: Added `CHECK (passenger_type IN ('adult', 'senior', 'disabled'))` in booking tables. Why: Prevents dirty data (like typos) from frontend bugs.
- **Concession Gate Verification (ENUM Status)**: Changed simple boolean to `concession_verification_status` ENUM (`not_required`, `pending_gate_check`, `verified_at_gate`). Why: A boolean `false` is ambiguous (normal adult vs unverified senior). This cleanly supports third-party booking (A buys for B) while ensuring an audit trail for manual gate checks.
- **Concurrent Wallet Deductions (Race Condition)**: Backend must use Pessimistic Locking (`SELECT ... FOR UPDATE`) when deducting `app_credit_balance`. Why: Prevents Lost Update problem when users purchase tickets simultaneously on Web and App.
- **Currency Standardization**: Standardized all references to USD. Changed `115 GBP` high-value threshold to `150 USD` in `lost_items` comment. Why: To align with the `amount_usd` columns defined in the schema.
- **Architectural Authorship Verification**: The "Architect Note: Concept Origination & Refinement" comment has been successfully verified to exist in databases/relational/schema.sql, skeleton/seed_postgres.py, and databases/relational/queries.py, confirming 10LJN09's original conceptualization and refinement. Why: To accurately reflect the history of the `schema-ex` branch where 10lJN09 drafted the core architecture, which was later adjusted and verified in this branch.
- **Utility Script**: Retained `generate_json.py` (moved to `scripts/` folder). Why: This script is a useful utility for generating dummy data for the `lost_items.json` and `penalties.json` files if we ever need to regenerate or expand the mock dataset.

## Prompts That Worked

<!-- Share prompts that produced good output so teammates can reuse them. -->

### Schema design prompt that worked:

```
TODO — add a prompt here after your schema design workshop
```

### Analytical and Multi-Option Discussion Prompt that worked:

```text
When evaluating system design choices (like database schema vs RAG, or discount application logic), please break down the analysis by proposing multiple distinct approaches (e.g., Option A vs. Option B). For each option, clearly explain the technical implications, required schema changes, and the exact timing/lifecycle of the business logic. Then, provide your explicit recommendation on which approach is best suited for our architecture, backed by specific rules from our JSON files.
```

### Query implementation prompt that worked:

```
TODO — add after implementing your first function
```

## Checklist

- [] national_rail_coaches and coach_name和national_rail_booking have the same meaning

```
現在的作法：訂單表記錄 coach = 'A'、seat_id = 'A05'，但沒有用外鍵 (Foreign Key) 綁定。
如果設計得更嚴謹：我們應該讓 national_rail_bookings 記錄一個 seat_id_fk (或者 coach_id_fk) 指向實體表。這樣一來，訂單表裡面就完全不需要存 coach 和 seat_id 字串了！要查詢車廂代號時，只要 JOIN 回 national_rail_coaches 讀取 coach_name 即可。這能避免「訂單寫車廂 B，但配置表說這班車只有車廂 A」這種不一致的錯誤。
```

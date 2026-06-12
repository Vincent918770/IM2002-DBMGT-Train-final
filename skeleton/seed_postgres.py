"""
Seed PostgreSQL with all TransitFlow mock data from train-mock-data/.

Usage:
    python skeleton/seed_postgres.py

Run AFTER docker-compose up -d.
You must first design and create your tables in databases/relational/schema.sql.
Safe to re-run: implement your inserts with ON CONFLICT DO NOTHING.
"""

# =========================================================================
# [ Architect Note: Concept Origination & Refinement ]
# The mock data integration, JSON parsing, and dynamic database seeding logic 
# of users, lost_items and penalties within this script were extensively modified and implemented by 
# Lucas (10LJN09) in this final version.
# =========================================================================

import json
import os
import sys

import psycopg2
from psycopg2.extras import execute_values

# argon2-cffi: Used for password hashing; requires "pip install argon2-cffi" first. ──
from argon2 import PasswordHasher

# ── resolve paths ────────────────────────────────────────────────────────────
SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
DATA_DIR    = os.path.join(PROJECT_DIR, "train-mock-data")

sys.path.insert(0, PROJECT_DIR)
from skeleton import config as cfg


def load(filename):
    with open(os.path.join(DATA_DIR, filename), encoding="utf-8") as f:
        return json.load(f)


def connect():
    return psycopg2.connect(
        host=cfg.PG_HOST,
        port=cfg.PG_PORT,
        dbname=cfg.PG_DB,
        user=cfg.PG_USER,
        password=cfg.PG_PASSWORD,
    )


def insert_many(cur, table, columns, rows):
    """Bulk insert with ON CONFLICT DO NOTHING. Returns row count inserted."""
    if not rows:
        return 0
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES %s "
        f"ON CONFLICT DO NOTHING"
    )
    execute_values(cur, sql, rows)
    return cur.rowcount


# ── seeders ──────────────────────────────────────────────────────────────────

def seed_metro_stations(cur):
    """Insert into metro_stations table. Ignore 'interchange_metro_lines' and 'adjacent_stations' in JSON (delegated to Neo4j).
    """
    data = load("metro_stations.json")
    columns = [
        "station_id",
        "name",
        "is_interchange_metro",
        "is_interchange_national_rail",
        "interchange_national_rail_station_id",
        "lines",
    ]
    rows = []
    for item in data:
        rows.append((
            item.get("station_id", None),
            item.get("name", None),
            item.get("is_interchange_metro", None),
            item.get("is_interchange_national_rail", None),
            item.get("interchange_national_rail_station_id", None),
            # The lines column is TEXT[] in the schema; passing a Python list lets psycopg2 convert it automatically
            item.get("lines", None),
        ))
    n = insert_many(cur, "metro_stations", columns, rows)
    print(f"  metro_stations: {n} rows inserted")


def seed_national_rail_stations(cur):
    """Insert into national_rail_stations table. Ignore 'interchange_national_rail_lines' and 'adjacent_stations' in JSON (delegated to Neo4j).
    """
    data = load("national_rail_stations.json")
    columns = [
        "station_id",
        "name",
        "is_interchange_national_rail",
        "is_interchange_metro",
        "interchange_metro_station_id",
        "lines",
    ]
    rows = []
    for item in data:
        rows.append((
            item.get("station_id", None),
            item.get("name", None),
            item.get("is_interchange_national_rail", None),
            item.get("is_interchange_metro", None),
            item.get("interchange_metro_station_id", None),
            item.get("lines", None),
        ))
    n = insert_many(cur, "national_rail_stations", columns, rows)
    print(f"  national_rail_stations: {n} rows inserted")


def seed_metro_schedules(cur):
    """Insert records into the main metro_schedules table, and unnest the arrays to insert into the metro_schedule_stops detail table.
    
    JSON Structure:
      - stops_in_order: ["MS20", "MS05", ...]          → Use enumerate() to get the stop_order
      - travel_time_from_origin_min: {"MS20": 0, ...}  → Use station_id as the key to look up travel time
    """
    data = load("metro_schedules.json")

    # ── main ──
    main_columns = [
        "schedule_id", "line", "direction",
        "origin_station_id", "destination_station_id",
        "first_train_time", "last_train_time",
        "base_fare_usd", "per_stop_rate_usd",
        "frequency_min", "operates_on",
    ]
    main_rows = []
    for item in data:
        main_rows.append((
            item.get("schedule_id", None),
            item.get("line", None),
            item.get("direction", None),
            item.get("origin_station_id", None),
            item.get("destination_station_id", None),
            item.get("first_train_time", None),
            item.get("last_train_time", None),
            item.get("base_fare_usd", None),
            item.get("per_stop_rate_usd", None),
            item.get("frequency_min", None),
            item.get("operates_on", None),
        ))
    n = insert_many(cur, "metro_schedules", main_columns, main_rows)
    print(f"  metro_schedules: {n} rows inserted")

    # ── metro_schedule_stops ──
    stop_columns = ["schedule_id", "station_id", "stop_order", "travel_time_from_origin_min"]
    stop_rows = []
    for item in data:
        schedule_id = item.get("schedule_id", None)
        stops_in_order = item.get("stops_in_order", [])
        travel_times = item.get("travel_time_from_origin_min", {})
        for idx, station_id in enumerate(stops_in_order):
            stop_rows.append((
                schedule_id,
                station_id,
                idx + 1,  
                travel_times.get(station_id, None),
            ))
    n = insert_many(cur, "metro_schedule_stops", stop_columns, stop_rows)
    print(f"  metro_schedule_stops: {n} rows inserted")


def seed_national_rail_schedules(cur):
    """nsert records into the main national_rail_schedules table, and unnest the data to insert into detail tables:
    1. national_rail_schedule_stops ─ stopping stations + passed-through stations
    2. national_rail_fares          ─ fares by ticket class
    Stopping stations (stops_in_order)                → is_passed_through = false
    Passed-through stations (passed_through_stations) → is_passed_through = true
    """
    data = load("national_rail_schedules.json")

    # ── main ──
    main_columns = [
        "schedule_id", "line", "service_type", "direction",
        "origin_station_id", "destination_station_id",
        "first_train_time", "last_train_time",
        "frequency_min", "operates_on",
    ]
    main_rows = []
    for item in data:
        main_rows.append((
            item.get("schedule_id", None),
            item.get("line", None),
            item.get("service_type", None),
            item.get("direction", None),
            item.get("origin_station_id", None),
            item.get("destination_station_id", None),
            item.get("first_train_time", None),
            item.get("last_train_time", None),
            item.get("frequency_min", None),
            item.get("operates_on", None),
        ))
    n = insert_many(cur, "national_rail_schedules", main_columns, main_rows)
    print(f"  national_rail_schedules: {n} rows inserted")

    # ── detail table 1: national_rail_schedule_stops ──
    # need to handle both stops_in_order (is_passed_through=false) and passed_through_stations (is_passed_through=true)
    stop_columns = [
        "schedule_id", "station_id", "stop_order",
        "travel_time_from_origin_min", "is_passed_through",
    ]
    stop_rows = []
    for item in data:
        schedule_id = item.get("schedule_id", None)
        stops_in_order = item.get("stops_in_order", [])
        travel_times = item.get("travel_time_from_origin_min", {})
        passed_through = item.get("passed_through_stations", [])

        # Create a combined list of all stations (including passed-through stations), sorted by travel time.
        # Stopping stations have explicit travel times; passed-through stations might also appear in travel_times (depending on the JSON).
        # To assign correct stop_order to passed-through stations, merge all stations and sort by travel time.
        all_stations_info = []

        # Add stopping stations
        for station_id in stops_in_order:
            all_stations_info.append({
                "station_id": station_id,
                "travel_time": travel_times.get(station_id, None),
                "is_passed_through": False,
            })

        # Add passed-through stations (will not appear in travel_times, travel_time set to None)
        for station_id in passed_through:
            all_stations_info.append({
                "station_id": station_id,
                "travel_time": travel_times.get(station_id, None),
                "is_passed_through": True,
            })

        # Sorted by travel time in ascending order, with None values placed at the end.
        all_stations_info.sort(key=lambda x: (x["travel_time"] is None, x["travel_time"] or 0))

        for idx, info in enumerate(all_stations_info):
            stop_rows.append((
                schedule_id,
                info["station_id"],
                idx + 1,
                info["travel_time"],
                info["is_passed_through"],
            ))

    n = insert_many(cur, "national_rail_schedule_stops", stop_columns, stop_rows)
    print(f"  national_rail_schedule_stops: {n} rows inserted")

    # ── detail table 2: national_rail_fares ──
    fare_columns = ["schedule_id", "fare_class", "base_fare_usd", "per_stop_rate_usd"]
    fare_rows = []
    for item in data:
        schedule_id = item.get("schedule_id", None)
        fare_classes = item.get("fare_classes", {})
        for fare_class, pricing in fare_classes.items():
            fare_rows.append((
                schedule_id,
                fare_class,
                pricing.get("base_fare_usd", None),
                pricing.get("per_stop_rate_usd", None),
            ))
    n = insert_many(cur, "national_rail_fares", fare_columns, fare_rows)
    print(f"  national_rail_fares: {n} rows inserted")


def seed_seat_layouts(cur):
    """Write to three tables:
    1. national_rail_seat_layouts ─ Seat layout main table
    2. national_rail_coaches      ─ Coach details (coach_id generated automatically by SERIAL)
    3. national_rail_seats         ─ Seat details

    Since the FK of national_rail_seats points to the SERIAL PK of national_rail_coaches,
    we need to INSERT a coach first and retrieve the generated coach_id before inserting seats.
    Therefore, coaches and seats use a row-by-row insertion strategy.
    """
    data = load("national_rail_seat_layouts.json")

    # ── Main table: national_rail_seat_layouts ──
    layout_columns = ["layout_id", "schedule_id"]
    layout_rows = []
    for item in data:
        layout_rows.append((
            item.get("layout_id", None),
            item.get("schedule_id", None),
        ))
    n = insert_many(cur, "national_rail_seat_layouts", layout_columns, layout_rows)
    print(f"  national_rail_seat_layouts: {n} rows inserted")

    # ── Detail tables: national_rail_coaches + national_rail_seats ──
    coach_insert_count = 0
    seat_insert_count = 0

    for item in data:
        layout_id = item.get("layout_id", None)
        coaches = item.get("coaches", [])

        for coach_data in coaches:
            coach_name = coach_data.get("coach", None)
            fare_class = coach_data.get("fare_class", None)

            # Insert the coach and retrieve the SERIAL-generated coach_id
            cur.execute(
                """
                INSERT INTO national_rail_coaches (layout_id, coach_name, fare_class)
                VALUES (%s, %s, %s)
                ON CONFLICT DO NOTHING
                RETURNING coach_id
                """,
                (layout_id, coach_name, fare_class),
            )
            result = cur.fetchone()
            if result is None:
                # Already exists (ON CONFLICT), query to obtain the coach_id
                cur.execute(
                    """
                    SELECT coach_id FROM national_rail_coaches
                    WHERE layout_id = %s AND coach_name = %s
                    """,
                    (layout_id, coach_name),
                )
                result = cur.fetchone()
                if result is None:
                    continue  # This should not happen in theory
            coach_id = result[0]
            coach_insert_count += 1

            # Insert all seats for this coach
            seats = coach_data.get("seats", [])
            seat_columns = ["seat_id", "coach_id", "row_num", "column_letter"]
            seat_rows = []
            for seat in seats:
                seat_rows.append((
                    seat.get("seat_id", None),
                    coach_id,
                    seat.get("row", None),
                    seat.get("column", None),
                ))
            if seat_rows:
                inserted = insert_many(cur, "national_rail_seats", seat_columns, seat_rows)
                seat_insert_count += inserted

    print(f"  national_rail_coaches: {coach_insert_count} rows processed")
    print(f"  national_rail_seats: {seat_insert_count} rows inserted")


def seed_users(cur):
    """Insert into users main table and users_confidential secret table.

    ── Password security design notes ──────────────────────────────────────────
    Uses the argon2id algorithm (argon2-cffi package) for password hashing.
    Reasons for choosing argon2id:
      1. Argon2 supports adjustable cost factors, including memory cost,
         time cost, and parallelism, which helps resist GPU/ASIC brute force attacks.
      2. The library automatically mixes a unique random salt into each password
         hash and packages the salt together with the hash result in a single string
         (format: $argon2id$v=...m=...t=...p=...$salt$hash).
         Therefore even identical passwords produce different hash strings,
         defending against rainbow table attacks.
      3. The schema does not expose a separate salt column, so storing the single
         hash string directly in users_confidential.password avoids manual salt handling.
    ──────────────────────────────────────────────────────────────────────────────
    """
    data = load("registered_users.json")

    # Initialize the Argon2 password hasher
    # PasswordHasher defaults to the argon2id variant with secure defaults:
    #   - time_cost=3
    #   - memory_cost=65536 (64 MB)
    #   - parallelism=4
    # These cost factors make brute force attacks computationally expensive.
    ph = PasswordHasher()

    # ── Main table: users ──
    user_columns = [
        "user_id", "full_name", "email", "phone",
        "date_of_birth", "registered_at", "is_active",
        "verified_concession", "app_credit_balance"
    ]
    user_rows = []
    for item in data:
        user_rows.append((
            item.get("user_id", None),
            item.get("full_name", None),
            item.get("email", None),
            item.get("phone", None),
            item.get("date_of_birth", None),
            item.get("registered_at", None),
            item.get("is_active", None),
            item.get("verified_concession", None),
            item.get("app_credit_balance", 1000.00),
        ))
    n = insert_many(cur, "users", user_columns, user_rows)
    print(f"  users: {n} rows inserted")

    # ── Secret table: users_confidential ──
    conf_columns = ["user_id", "password", "secret_question", "secret_answer"]
    conf_rows = []
    for item in data:
        raw_password = item.get("password", None)
        raw_secret_answer = item.get("secret_answer", None)

        # Use argon2id to hash passwords:
        # ph.hash() automatically generates a random salt and packages it with the hash result
        # so identical passwords produce different hashes, defending against rainbow table attacks.
        hashed_password = ph.hash(raw_password) if raw_password else None
        hashed_secret_answer = ph.hash(raw_secret_answer.strip().lower()) if raw_secret_answer else None

        conf_rows.append((
            item.get("user_id", None),
            hashed_password,
            item.get("secret_question", None),
            hashed_secret_answer,
        ))
    n = insert_many(cur, "users_confidential", conf_columns, conf_rows)
    print(f"  users_confidential: {n} rows inserted")


def seed_national_rail_bookings(cur):
    """Insert into national_rail_bookings table."""
    data = load("bookings.json")
    columns = [
        "booking_id", "user_id", "schedule_id",
        "origin_station_id", "destination_station_id",
        "travel_date", "departure_time",
        "ticket_type", "passenger_type", "interchange_discount_applied",
        "linked_trip_id", "fare_class", "coach", "seat_id",
        "concession_verification_status", "stops_travelled",
        "amount_usd", "status", "booked_at", "travelled_at",
    ]
    rows = []
    for item in data:
        rows.append((
            item.get("booking_id", None),
            item.get("user_id", None),
            item.get("schedule_id", None),
            item.get("origin_station_id", None),
            item.get("destination_station_id", None),
            item.get("travel_date", None),
            item.get("departure_time", None),
            item.get("ticket_type", None),
            item.get("passenger_type", "adult"),
            item.get("interchange_discount_applied", False),
            item.get("linked_trip_id", None),
            item.get("fare_class", None),
            item.get("coach", None),
            item.get("seat_id", None),
            item.get("concession_verification_status", "not_required"),
            item.get("stops_travelled", None),
            item.get("amount_usd", None),
            item.get("status", None),
            item.get("booked_at", None),
            item.get("travelled_at", None),
        ))
    n = insert_many(cur, "national_rail_bookings", columns, rows)
    print(f"  national_rail_bookings: {n} rows inserted")


def seed_metro_travels(cur):
    """Insert into metro_travel_history table.

    Special handling: day_pass_ref is a self-referencing foreign key.
    To avoid FK violations, insert in two batches:
      1. Insert records without day_pass_ref first (or where day_pass_ref is null)
      2. Then insert records with day_pass_ref once the referenced trip_id exists
    """
    data = load("metro_travel_history.json")
    columns = [
        "trip_id", "user_id", "schedule_id",
        "origin_station_id", "destination_station_id",
        "travel_date", "ticket_type", "passenger_type",
        "day_pass_ref", "interchange_discount_applied",
        "linked_trip_id", "concession_verification_status",
        "stops_travelled", "amount_usd", "status",
        "purchased_at", "travelled_at",
    ]

    # Split into two batches: insert rows without day_pass_ref first, then rows with day_pass_ref
    rows_no_ref = []
    rows_with_ref = []

    for item in data:
        row = (
            item.get("trip_id", None),
            item.get("user_id", None),
            item.get("schedule_id", None),
            item.get("origin_station_id", None),
            item.get("destination_station_id", None),
            item.get("travel_date", None),
            item.get("ticket_type", None),
            item.get("passenger_type", "adult"),
            item.get("day_pass_ref", None),
            item.get("interchange_discount_applied", False),
            item.get("linked_trip_id", None),
            item.get("concession_verification_status", "not_required"),
            item.get("stops_travelled", None),
            item.get("amount_usd", None),
            item.get("status", None),
            item.get("purchased_at", None),
            item.get("travelled_at", None),
        )
        if item.get("day_pass_ref", None) is not None:
            rows_with_ref.append(row)
        else:
            rows_no_ref.append(row)

    n1 = insert_many(cur, "metro_travel_history", columns, rows_no_ref)
    n2 = insert_many(cur, "metro_travel_history", columns, rows_with_ref)
    print(f"  metro_travel_history: {n1 + n2} rows inserted ({n1} base + {n2} day_pass refs)")


def seed_payments(cur):
    """Insert into payments table."""
    data = load("payments.json")
    columns = [
        "payment_id", "booking_id", "amount_usd",
        "method", "status", "paid_at",
    ]
    rows = []
    for item in data:
        rows.append((
            item.get("payment_id", None),
            item.get("booking_id", None),
            item.get("amount_usd", None),
            item.get("method", None),
            item.get("status", None),
            item.get("paid_at", None),
        ))
    n = insert_many(cur, "payments", columns, rows)
    print(f"  payments: {n} rows inserted")


def seed_feedback(cur):
    """Insert into feedback table."""
    data = load("feedback.json")
    columns = [
        "feedback_id", "booking_id", "user_id",
        "rating", "comment", "submitted_at",
    ]
    rows = []
    for item in data:
        rows.append((
            item.get("feedback_id", None),
            item.get("booking_id", None),
            item.get("user_id", None),
            item.get("rating", None),
            item.get("comment", None),
            item.get("submitted_at", None),
        ))
    n = insert_many(cur, "feedback", columns, rows)
    print(f"  feedback: {n} rows inserted")


def seed_lost_items(cur):
    """寫入 lost_items 表。"""
    data = load("lost_items.json")
    columns = [
        "item_id", "found_date", "reported_date", "station_id",
        "category", "description", "is_high_value", "has_personal_info",
        "status", "claimed_by_user", "claimed_date"
    ]
    rows = []
    for item in data:
        rows.append((
            item.get("item_id"),
            item.get("found_date"),
            item.get("reported_date"),
            item.get("station_id"),
            item.get("category"),
            item.get("description"),
            item.get("is_high_value", False),
            item.get("has_personal_info", False),
            item.get("status", "reported"),
            item.get("claimed_by_user"),
            item.get("claimed_date")
        ))
    n = insert_many(cur, "lost_items", columns, rows)
    print(f"  lost_items: {n} rows inserted")


def seed_penalties(cur):
    """寫入 penalties 表。"""
    data = load("penalties.json")
    columns = [
        "penalty_id", "user_id", "violation_type", "violation_date",
        "location", "amount_usd", "status", "due_date", "paid_at"
    ]
    rows = []
    for item in data:
        rows.append((
            item.get("penalty_id"),
            item.get("user_id"),
            item.get("violation_type"),
            item.get("violation_date"),
            item.get("location"),
            item.get("amount_usd"),
            item.get("status", "unpaid"),
            item.get("due_date"),
            item.get("paid_at")
        ))
    n = insert_many(cur, "penalties", columns, rows)
    print(f"  penalties: {n} rows inserted")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    print("Connecting to PostgreSQL...")
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("Seeding tables (dependency order):")

        # ── First layer: base tables with no foreign key dependencies ──
        seed_metro_stations(cur)           # metro_stations (referenced by metro_schedules and metro_travel_history)
        seed_national_rail_stations(cur)   # national_rail_stations (referenced by national_rail_schedules and bookings)
        seed_users(cur)                    # users + users_confidential (referenced by bookings, metro_travel_history, feedback)

        # ── Second layer: schedules that depend on the first layer ──
        seed_metro_schedules(cur)          # metro_schedules + metro_schedule_stops (depends on metro_stations)
        seed_national_rail_schedules(cur)  # national_rail_schedules + schedule_stops + fares (depends on national_rail_stations)

        # ── Third layer: seat layout data that depends on the second layer ──
        seed_seat_layouts(cur)             # seat_layouts + coaches + seats (depends on national_rail_schedules)

        # ── Fourth layer: transaction records that depend on users and schedules ──
        seed_national_rail_bookings(cur)   # national_rail_bookings (depends on users, national_rail_schedules, national_rail_stations)
        seed_metro_travels(cur)            # metro_travel_history (depends on users, metro_schedules, metro_stations; includes self-ref FK)

        # ── Fifth layer: follow-up tables that depend on transaction records ──
        seed_payments(cur)                 # payments (booking_id has no strict FK constraint, but logically depends on bookings/metro_travel_history)
        seed_feedback(cur)                 # feedback (depends on users; booking_id has no strict FK)
        seed_lost_items(cur)               # lost_items (depends on stations, users)
        seed_penalties(cur)                # penalties (depends on users)

        conn.commit()
        print("\nAll done. Database seeded successfully.")
    except Exception as e:
        conn.rollback()
        print(f"\nError: {e}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()

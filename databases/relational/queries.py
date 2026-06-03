"""
TransitFlow — PostgreSQL / Relational Database Layer
=====================================================
This module handles all queries to PostgreSQL.

TWO ROLES ARE SERVED HERE:
  1. Relational  → dual-network transit (metro + national rail),
                   availability, fares, bookings, seat selection
  2. Vector      → policy document similarity search (pgvector)

STUDENT TASK
------------
Design your schema in databases/relational/schema.sql, seed it with
skeleton/seed_postgres.py, then implement the query functions below.

Functions prefixed with `query_`  are read-only lookups called by the agent.
Functions prefixed with `execute_` are write operations (booking/cancellation).

The vector functions (query_policy_vector_search, store_policy_document)
are already implemented — do not modify them.
"""

from __future__ import annotations

import json
import random
import string
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras

from skeleton.config import PG_DSN, VECTOR_TOP_K, VECTOR_SIMILARITY_THRESHOLD

# ── argon2-cffi: for verifying hashed passwords (seeded via seed_postgres.py) ─
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

_ph = PasswordHasher()


def _connect():
    """Return a new psycopg2 connection with autocommit enabled."""
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = True
    return conn


def _gen_booking_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"BK-{suffix}"


def _gen_payment_id() -> str:
    suffix = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f"PM-{suffix}"


# ── Example ───────────────────────────────────────────────────────────────────
# The block below shows the query pattern: open a cursor, run SQL, return rows.
# Use _connect() for read-only queries; for write operations use a manual
# connection with conn.commit() / conn.rollback() (see execute_booking below).

def example_query() -> dict:
    """Example: returns the name of the connected database."""
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT current_database() AS db;")
            return dict(cur.fetchone())


# ── NATIONAL RAIL AVAILABILITY ────────────────────────────────────────────────

def query_national_rail_availability(
    origin_id: str,
    destination_id: str,
    travel_date: Optional[str] = None,
) -> list[dict]:
    """
    Return national rail schedules that serve both origin and destination stations
    in the correct order, along with seat occupancy for the requested travel date.

    Args:
        origin_id:       e.g. "NR01"
        destination_id:  e.g. "NR05"
        travel_date:     e.g. "2025-06-01" — used to count bookings; omit for general info
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # Find schedules where origin appears BEFORE destination in the stops list.
            # We join national_rail_schedule_stops twice (aliased as o and d) to ensure
            # origin stop_order < destination stop_order, and neither is a passed-through stop.
            sql = """
                SELECT
                    s.schedule_id,
                    s.line,
                    s.service_type,
                    s.direction,
                    s.first_train_time::text,
                    s.last_train_time::text,
                    s.frequency_min,
                    s.operates_on,
                    orig_st.name  AS origin_name,
                    dest_st.name  AS destination_name,
                    o.stop_order  AS origin_stop_order,
                    d.stop_order  AS destination_stop_order,
                    (d.stop_order - o.stop_order) AS stops_travelled
                FROM national_rail_schedules s
                -- Origin stop: must be a real stop (not passed-through)
                JOIN national_rail_schedule_stops o
                    ON o.schedule_id = s.schedule_id
                    AND o.station_id = %s
                    AND o.is_passed_through = FALSE
                -- Destination stop: must be a real stop (not passed-through)
                JOIN national_rail_schedule_stops d
                    ON d.schedule_id = s.schedule_id
                    AND d.station_id = %s
                    AND d.is_passed_through = FALSE
                -- Origin must come before destination
                JOIN national_rail_stations orig_st ON orig_st.station_id = %s
                JOIN national_rail_stations dest_st ON dest_st.station_id = %s
                WHERE o.stop_order < d.stop_order
                ORDER BY s.service_type, s.first_train_time
            """
            cur.execute(sql, (origin_id, destination_id, origin_id, destination_id))
            schedules = [dict(row) for row in cur.fetchall()]

            if not schedules:
                return []

            # If a travel_date is provided, also count confirmed bookings per schedule
            # to indicate how busy each service is.
            if travel_date:
                for sched in schedules:
                    cur.execute("""
                        SELECT COUNT(*) AS booked_seats
                        FROM national_rail_bookings
                        WHERE schedule_id = %s
                          AND travel_date = %s
                          AND status = 'confirmed'
                    """, (sched["schedule_id"], travel_date))
                    row = cur.fetchone()
                    sched["booked_seats_on_date"] = row["booked_seats"] if row else 0

            return schedules


def query_national_rail_fare(
    schedule_id: str,
    fare_class: str,
    stops_travelled: int,
) -> Optional[dict]:
    """
    Calculate the fare for a national rail journey.

    Args:
        schedule_id:     e.g. "NR_SCH01"
        fare_class:      "standard" or "first"
        stops_travelled: number of stops between origin and destination (inclusive)

    Returns:
        dict with fare_class, base_fare_usd, per_stop_rate_usd, total_fare_usd
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT fare_class, base_fare_usd, per_stop_rate_usd
                FROM national_rail_fares
                WHERE schedule_id = %s AND fare_class = %s
            """, (schedule_id, fare_class))
            row = cur.fetchone()

            if row is None:
                return None

            # Total fare = base + (per_stop_rate * stops_travelled)
            total = float(row["base_fare_usd"]) + float(row["per_stop_rate_usd"]) * stops_travelled
            return {
                "schedule_id": schedule_id,
                "fare_class": row["fare_class"],
                "base_fare_usd": float(row["base_fare_usd"]),
                "per_stop_rate_usd": float(row["per_stop_rate_usd"]),
                "stops_travelled": stops_travelled,
                "total_fare_usd": round(total, 2),
            }


# ── METRO SCHEDULES & FARE ────────────────────────────────────────────────────

def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:
    """
    Return metro schedules that serve both origin and destination in the correct order.

    Args:
        origin_id:       e.g. "MS01"
        destination_id:  e.g. "MS09"
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Same pattern as national rail: join stops twice to confirm order
            sql = """
                SELECT
                    s.schedule_id,
                    s.line,
                    s.direction,
                    s.first_train_time::text,
                    s.last_train_time::text,
                    s.frequency_min,
                    s.operates_on,
                    s.base_fare_usd,
                    s.per_stop_rate_usd,
                    orig_st.name AS origin_name,
                    dest_st.name AS destination_name,
                    o.stop_order AS origin_stop_order,
                    d.stop_order AS destination_stop_order,
                    (d.stop_order - o.stop_order) AS stops_travelled
                FROM metro_schedules s
                JOIN metro_schedule_stops o
                    ON o.schedule_id = s.schedule_id AND o.station_id = %s
                JOIN metro_schedule_stops d
                    ON d.schedule_id = s.schedule_id AND d.station_id = %s
                JOIN metro_stations orig_st ON orig_st.station_id = %s
                JOIN metro_stations dest_st ON dest_st.station_id = %s
                WHERE o.stop_order < d.stop_order
                ORDER BY s.line, s.first_train_time
            """
            cur.execute(sql, (origin_id, destination_id, origin_id, destination_id))
            return [dict(row) for row in cur.fetchall()]


def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]:
    """
    Calculate the metro fare for a single-ticket journey.

    Args:
        schedule_id:     e.g. "MS_SCH01"
        stops_travelled: number of stops between origin and destination

    Returns:
        dict with base_fare_usd, per_stop_rate_usd, total_fare_usd
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT base_fare_usd, per_stop_rate_usd
                FROM metro_schedules
                WHERE schedule_id = %s
            """, (schedule_id,))
            row = cur.fetchone()

            if row is None:
                return None

            total = float(row["base_fare_usd"]) + float(row["per_stop_rate_usd"]) * stops_travelled
            return {
                "schedule_id": schedule_id,
                "base_fare_usd": float(row["base_fare_usd"]),
                "per_stop_rate_usd": float(row["per_stop_rate_usd"]),
                "stops_travelled": stops_travelled,
                "total_fare_usd": round(total, 2),
            }


# ── SEAT SELECTION ────────────────────────────────────────────────────────────

def query_available_seats(
    schedule_id: str,
    travel_date: str,
    fare_class: str,
) -> list[dict]:
    """
    Return available seats for a national rail journey on a given date.

    Args:
        schedule_id:  e.g. "NR_SCH01"
        travel_date:  e.g. "2025-06-01"
        fare_class:   "standard" or "first"

    Returns:
        List of dicts: {seat_id, coach, row, column}
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # Find all seats in coaches matching the fare_class for this schedule's layout.
            # Then exclude any seat already booked (confirmed) on the given date.
            sql = """
                SELECT
                    ns.seat_id,
                    nc.coach_name AS coach,
                    ns.row_num    AS row,
                    ns.column_letter AS column
                FROM national_rail_seat_layouts nsl
                JOIN national_rail_coaches nc
                    ON nc.layout_id = nsl.layout_id AND nc.fare_class = %s
                JOIN national_rail_seats ns
                    ON ns.coach_id = nc.coach_id
                WHERE nsl.schedule_id = %s
                  AND ns.seat_id NOT IN (
                      -- Exclude seats already booked for this schedule + date
                      SELECT seat_id
                      FROM national_rail_bookings
                      WHERE schedule_id = %s
                        AND travel_date = %s
                        AND status = 'confirmed'
                  )
                ORDER BY nc.coach_name, ns.row_num, ns.column_letter
            """
            cur.execute(sql, (fare_class, schedule_id, schedule_id, travel_date))
            return [dict(row) for row in cur.fetchall()]


def auto_select_adjacent_seats(available_seats: list[dict], count: int) -> list[str]:
    """
    Select `count` seats that are as close together as possible (same row preferred,
    then adjacent rows). Returns a list of seat_ids.

    Args:
        available_seats: output of query_available_seats()
        count:           number of seats needed
    """
    if not available_seats or count <= 0:
        return []
    if count >= len(available_seats):
        return [s["seat_id"] for s in available_seats[:count]]

    from collections import defaultdict
    rows: dict[int, list[dict]] = defaultdict(list)
    for seat in available_seats:
        rows[seat["row"]].append(seat)

    for row_seats in sorted(rows.values(), key=lambda s: s[0]["row"]):
        if len(row_seats) >= count:
            return [s["seat_id"] for s in row_seats[:count]]

    sorted_seats = sorted(available_seats, key=lambda s: (s["row"], s["column"]))
    return [s["seat_id"] for s in sorted_seats[:count]]


# ── USER & BOOKING QUERIES ────────────────────────────────────────────────────

def query_user_profile(user_email: str) -> Optional[dict]:
    """Return a user's profile by email."""
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT user_id, full_name, email, phone, date_of_birth,
                       registered_at, is_active
                FROM users
                WHERE email = %s
            """, (user_email,))
            row = cur.fetchone()
            return dict(row) if row else None


def query_user_bookings(user_email: str) -> dict:
    """
    Return a user's combined booking history (national rail + metro).

    Returns:
        dict with keys 'national_rail' (list) and 'metro' (list)
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # Resolve email → user_id first
            cur.execute("SELECT user_id FROM users WHERE email = %s", (user_email,))
            user_row = cur.fetchone()
            if user_row is None:
                return {"national_rail": [], "metro": []}

            user_id = user_row["user_id"]

            # National rail bookings — join station names for readability
            cur.execute("""
                SELECT
                    b.booking_id,
                    b.schedule_id,
                    b.travel_date::text,
                    b.departure_time::text,
                    b.ticket_type,
                    b.fare_class,
                    b.coach,
                    b.seat_id,
                    b.stops_travelled,
                    b.amount_usd,
                    b.status,
                    b.booked_at::text,
                    orig.name AS origin_name,
                    orig.station_id AS origin_station_id,
                    dest.name AS destination_name,
                    dest.station_id AS destination_station_id
                FROM national_rail_bookings b
                JOIN national_rail_stations orig ON orig.station_id = b.origin_station_id
                JOIN national_rail_stations dest ON dest.station_id = b.destination_station_id
                WHERE b.user_id = %s
                ORDER BY b.travel_date DESC, b.booked_at DESC
            """, (user_id,))
            nr_bookings = [dict(row) for row in cur.fetchall()]

            # Metro travel history — join station names for readability
            cur.execute("""
                SELECT
                    m.trip_id,
                    m.schedule_id,
                    m.travel_date::text,
                    m.ticket_type,
                    m.day_pass_ref,
                    m.stops_travelled,
                    m.amount_usd,
                    m.status,
                    m.purchased_at::text,
                    m.travelled_at::text,
                    orig.name AS origin_name,
                    orig.station_id AS origin_station_id,
                    dest.name AS destination_name,
                    dest.station_id AS destination_station_id
                FROM metro_travel_history m
                JOIN metro_stations orig ON orig.station_id = m.origin_station_id
                JOIN metro_stations dest ON dest.station_id = m.destination_station_id
                WHERE m.user_id = %s
                ORDER BY m.travel_date DESC, m.purchased_at DESC
            """, (user_id,))
            metro_trips = [dict(row) for row in cur.fetchall()]

            return {"national_rail": nr_bookings, "metro": metro_trips}


def query_payment_info(booking_id: str) -> Optional[dict]:
    """Return payment record for a booking or metro trip."""
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("""
                SELECT payment_id, booking_id, amount_usd,
                       method, status, paid_at::text
                FROM payments
                WHERE booking_id = %s
            """, (booking_id,))
            row = cur.fetchone()
            return dict(row) if row else None


# ── TRANSACTIONAL OPERATIONS ──────────────────────────────────────────────────

def execute_booking(
    user_id: str,
    schedule_id: str,
    origin_station_id: str,
    destination_station_id: str,
    travel_date: str,
    fare_class: str,
    seat_id: str,
    ticket_type: str = "single",
) -> tuple[bool, dict | str]:
    """
    Create a national rail booking for a logged-in user.

    Args:
        user_id:                e.g. "RU01" — must match the logged-in user
        schedule_id:            e.g. "NR_SCH01"
        origin_station_id:      e.g. "NR01"
        destination_station_id: e.g. "NR05"
        travel_date:            e.g. "2025-06-01"
        fare_class:             "standard" or "first"
        seat_id:                e.g. "B05" (or "any" to auto-assign)
        ticket_type:            "single" (default) or "return"

    Returns:
        (True, booking_dict)   on success
        (False, error_message) on failure
    """
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # 1. Verify user exists and is active
            cur.execute("SELECT user_id, is_active FROM users WHERE user_id = %s", (user_id,))
            user = cur.fetchone()
            if user is None:
                return False, f"User '{user_id}' not found."
            if not user["is_active"]:
                return False, f"User '{user_id}' account is inactive."

            # 2. Verify schedule exists and origin/destination are valid ordered stops
            cur.execute("""
                SELECT o.stop_order AS orig_order, d.stop_order AS dest_order,
                       (d.stop_order - o.stop_order) AS stops_travelled,
                       s.first_train_time::text AS departure_time
                FROM national_rail_schedules s
                JOIN national_rail_schedule_stops o
                    ON o.schedule_id = s.schedule_id
                    AND o.station_id = %s AND o.is_passed_through = FALSE
                JOIN national_rail_schedule_stops d
                    ON d.schedule_id = s.schedule_id
                    AND d.station_id = %s AND d.is_passed_through = FALSE
                WHERE s.schedule_id = %s AND o.stop_order < d.stop_order
            """, (origin_station_id, destination_station_id, schedule_id))
            stops_info = cur.fetchone()
            if stops_info is None:
                return False, (
                    f"Schedule '{schedule_id}' does not serve '{origin_station_id}' → "
                    f"'{destination_station_id}' in that order."
                )
            stops_travelled = stops_info["stops_travelled"]
            departure_time = stops_info["departure_time"]

            # 3. Calculate fare
            cur.execute("""
                SELECT base_fare_usd, per_stop_rate_usd
                FROM national_rail_fares
                WHERE schedule_id = %s AND fare_class = %s
            """, (schedule_id, fare_class))
            fare_row = cur.fetchone()
            if fare_row is None:
                return False, f"Fare class '{fare_class}' not available on schedule '{schedule_id}'."
            amount = float(fare_row["base_fare_usd"]) + float(fare_row["per_stop_rate_usd"]) * stops_travelled
            amount = round(amount, 2)

            # 4. Handle seat selection — auto-assign if "any" requested
            if seat_id.lower() == "any":
                available = query_available_seats(schedule_id, travel_date, fare_class)
                if not available:
                    return False, "No available seats for this journey."
                seat_id = available[0]["seat_id"]
            else:
                # Verify the requested seat is not already booked
                cur.execute("""
                    SELECT 1 FROM national_rail_bookings
                    WHERE schedule_id = %s AND travel_date = %s
                      AND seat_id = %s AND status = 'confirmed'
                """, (schedule_id, travel_date, seat_id))
                if cur.fetchone():
                    return False, f"Seat '{seat_id}' is already booked for this journey."

            # 5. Determine coach from seat layout
            cur.execute("""
                SELECT nc.coach_name
                FROM national_rail_seats ns
                JOIN national_rail_coaches nc ON nc.coach_id = ns.coach_id
                JOIN national_rail_seat_layouts nsl ON nsl.layout_id = nc.layout_id
                WHERE nsl.schedule_id = %s AND ns.seat_id = %s
                LIMIT 1
            """, (schedule_id, seat_id))
            coach_row = cur.fetchone()
            coach = coach_row["coach_name"] if coach_row else None

            # 6. Insert booking record with a generated unique booking_id
            booking_id = _gen_booking_id()
            booked_at = datetime.now(timezone.utc).isoformat()
            cur.execute("""
                INSERT INTO national_rail_bookings (
                    booking_id, user_id, schedule_id,
                    origin_station_id, destination_station_id,
                    travel_date, departure_time, ticket_type, fare_class,
                    coach, seat_id, stops_travelled, amount_usd, status, booked_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'confirmed', %s)
            """, (
                booking_id, user_id, schedule_id,
                origin_station_id, destination_station_id,
                travel_date, departure_time, ticket_type, fare_class,
                coach, seat_id, stops_travelled, amount, booked_at,
            ))

            # 7. Insert a corresponding payment record
            payment_id = _gen_payment_id()
            cur.execute("""
                INSERT INTO payments (payment_id, booking_id, amount_usd, method, status, paid_at)
                VALUES (%s, %s, %s, 'card', 'completed', %s)
            """, (payment_id, booking_id, amount, booked_at))

            conn.commit()
            return True, {
                "booking_id": booking_id,
                "payment_id": payment_id,
                "user_id": user_id,
                "schedule_id": schedule_id,
                "origin_station_id": origin_station_id,
                "destination_station_id": destination_station_id,
                "travel_date": travel_date,
                "departure_time": departure_time,
                "fare_class": fare_class,
                "ticket_type": ticket_type,
                "seat_id": seat_id,
                "coach": coach,
                "stops_travelled": stops_travelled,
                "amount_usd": amount,
                "status": "confirmed",
                "booked_at": booked_at,
            }

    except Exception as e:
        conn.rollback()
        return False, f"Booking failed due to a database error: {e}"
    finally:
        conn.close()


def execute_cancellation(booking_id: str, user_id: str) -> tuple[bool, dict | str]:
    """
    Cancel a national rail booking owned by the given user.

    Calculates the refund amount according to the booking's service type:
      - Normal service: RF001 windows (100% / 75% / 50% / 0%)
      - Express service: RF002 windows (100% / 50% / 0%)

    Args:
        booking_id: e.g. "BK001"
        user_id:    must match the booking's user_id

    Returns:
        (True, result_dict)  with refund_amount_usd and policy note
        (False, error_msg)
    """
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # 1. Fetch the booking and verify ownership
            cur.execute("""
                SELECT b.booking_id, b.user_id, b.amount_usd, b.status,
                       b.travel_date, b.departure_time,
                       s.service_type
                FROM national_rail_bookings b
                JOIN national_rail_schedules s ON s.schedule_id = b.schedule_id
                WHERE b.booking_id = %s
            """, (booking_id,))
            booking = cur.fetchone()

            if booking is None:
                return False, f"Booking '{booking_id}' not found."
            if booking["user_id"] != user_id:
                return False, "You are not authorised to cancel this booking."
            if booking["status"] != "confirmed":
                return False, f"Booking '{booking_id}' cannot be cancelled (status: {booking['status']})."

            # 2. Calculate hours until departure to determine the refund window
            now_utc = datetime.now(timezone.utc)
            departure_dt_str = f"{booking['travel_date']} {booking['departure_time']}"
            departure_naive = datetime.strptime(str(departure_dt_str), "%Y-%m-%d %H:%M:%S")
            departure_utc = departure_naive.replace(tzinfo=timezone.utc)
            hours_until_departure = (departure_utc - now_utc).total_seconds() / 3600

            service_type = booking["service_type"]  # "normal" or "express"
            amount = float(booking["amount_usd"])

            # 3. Apply refund policy based on service type (RF001 = normal, RF002 = express)
            if service_type == "normal":
                # RF001 windows
                if hours_until_departure >= 48:
                    refund_pct, admin_fee, policy_note = 100, 0.00, "RF001_W1: ≥48h → 100% refund, no fee"
                elif hours_until_departure >= 24:
                    refund_pct, admin_fee, policy_note = 75, 0.50, "RF001_W2: 24–48h → 75% refund, $0.50 fee"
                elif hours_until_departure >= 2:
                    refund_pct, admin_fee, policy_note = 50, 0.50, "RF001_W3: 2–24h → 50% refund, $0.50 fee"
                else:
                    refund_pct, admin_fee, policy_note = 0, 0.00, "RF001_W4: <2h or past departure → no refund"
            else:
                # RF002 windows (express — stricter)
                if hours_until_departure >= 48:
                    refund_pct, admin_fee, policy_note = 100, 1.00, "RF002_W1: ≥48h → 100% refund, $1.00 fee"
                elif hours_until_departure >= 24:
                    refund_pct, admin_fee, policy_note = 50, 1.00, "RF002_W2: 24–48h → 50% refund, $1.00 fee"
                else:
                    refund_pct, admin_fee, policy_note = 0, 0.00, "RF002_W3: <24h or past departure → no refund"

            refund_amount = round(max(0.0, (amount * refund_pct / 100) - admin_fee), 2)

            # 4. Update booking status to 'cancelled'
            cur.execute("""
                UPDATE national_rail_bookings SET status = 'cancelled'
                WHERE booking_id = %s
            """, (booking_id,))

            # 5. Record refund as a payment entry (negative amount = refund)
            if refund_amount > 0:
                payment_id = _gen_payment_id()
                cancelled_at = datetime.now(timezone.utc).isoformat()
                cur.execute("""
                    INSERT INTO payments (payment_id, booking_id, amount_usd, method, status, paid_at)
                    VALUES (%s, %s, %s, 'refund', 'completed', %s)
                """, (payment_id, booking_id, -refund_amount, cancelled_at))

            conn.commit()
            return True, {
                "booking_id": booking_id,
                "original_amount_usd": amount,
                "refund_percent": refund_pct,
                "admin_fee_usd": admin_fee,
                "refund_amount_usd": refund_amount,
                "policy_applied": policy_note,
                "hours_until_departure": round(hours_until_departure, 1),
                "status": "cancelled",
            }

    except Exception as e:
        conn.rollback()
        return False, f"Cancellation failed due to a database error: {e}"
    finally:
        conn.close()


# ── AUTHENTICATION QUERIES ────────────────────────────────────────────────────

def register_user(
    email: str,
    first_name: str,
    surname: str,
    year_of_birth: int,
    password: str,
    secret_question: str,
    secret_answer: str,
) -> tuple[bool, str]:
    """
    Register a new user.
    Returns (True, user_id) on success or (False, error_message) on failure.

    Passwords and secret answers are stored as argon2id hashes (matching seed_postgres.py).
    """
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:

            # Check for duplicate email
            cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return False, f"An account with email '{email}' already exists."

            # Generate a user_id in the format RU<nn>
            cur.execute("SELECT COUNT(*) FROM users")
            count = cur.fetchone()[0]
            new_user_id = f"RU{count + 1:02d}"

            full_name = f"{first_name} {surname}"
            # Build a date_of_birth from year_of_birth (use Jan 1 as placeholder)
            date_of_birth = f"{year_of_birth}-01-01"
            registered_at = datetime.now(timezone.utc).isoformat()

            # Insert into users table
            cur.execute("""
                INSERT INTO users (user_id, full_name, email, date_of_birth, registered_at, is_active)
                VALUES (%s, %s, %s, %s, %s, TRUE)
            """, (new_user_id, full_name, email, date_of_birth, registered_at))

            # Hash password and secret_answer using argon2id (same as seed_postgres.py)
            hashed_password = _ph.hash(password)
            hashed_answer = _ph.hash(secret_answer.lower().strip())

            # Insert into users_confidential table
            cur.execute("""
                INSERT INTO users_confidential (user_id, password, secret_question, secret_answer)
                VALUES (%s, %s, %s, %s)
            """, (new_user_id, hashed_password, secret_question, hashed_answer))

            conn.commit()
            return True, new_user_id

    except Exception as e:
        conn.rollback()
        return False, f"Registration failed: {e}"
    finally:
        conn.close()


def login_user(email: str, password: str) -> Optional[dict]:
    """
    Verify credentials. Returns a user dict on success or None on failure.
    Dict keys: user_id, email, full_name, first_name, surname, phone, date_of_birth, is_active.
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:

            # Fetch user profile and hashed password together via JOIN
            cur.execute("""
                SELECT u.user_id, u.full_name, u.email, u.phone, u.date_of_birth,
                       u.registered_at, u.is_active,
                       uc.password AS hashed_password
                FROM users u
                JOIN users_confidential uc ON uc.user_id = u.user_id
                WHERE u.email = %s
            """, (email,))
            row = cur.fetchone()

            if row is None:
                return None  # Email not found

            if not row["is_active"]:
                return None  # Account is deactivated

            # Verify the provided password against the argon2id hash
            try:
                _ph.verify(row["hashed_password"], password)
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return None  # Wrong password

            # Split full_name into first_name / surname for the agent context
            name_parts = row["full_name"].split(" ", 1)
            first_name = name_parts[0]
            surname = name_parts[1] if len(name_parts) > 1 else ""

            return {
                "user_id": row["user_id"],
                "email": row["email"],
                "full_name": row["full_name"],
                "first_name": first_name,
                "surname": surname,
                "phone": row["phone"],
                "date_of_birth": str(row["date_of_birth"]) if row["date_of_birth"] else None,
                "is_active": row["is_active"],
            }


def get_user_secret_question(email: str) -> Optional[str]:
    """Return the secret question for a registered email, or None if not found."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT uc.secret_question
                FROM users u
                JOIN users_confidential uc ON uc.user_id = u.user_id
                WHERE u.email = %s
            """, (email,))
            row = cur.fetchone()
            return row[0] if row else None


def verify_secret_answer(email: str, answer: str) -> bool:
    """Return True if the provided answer matches the stored secret answer (case-insensitive)."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT uc.secret_answer
                FROM users u
                JOIN users_confidential uc ON uc.user_id = u.user_id
                WHERE u.email = %s
            """, (email,))
            row = cur.fetchone()
            if row is None:
                return False

            # Compare using argon2 verify (case-insensitive: normalise both to lower)
            try:
                _ph.verify(row[0], answer.lower().strip())
                return True
            except (VerifyMismatchError, VerificationError, InvalidHashError):
                return False


def update_password(email: str, new_password: str) -> bool:
    """Update the password for a user. Returns True if the row was updated."""
    conn = psycopg2.connect(PG_DSN)
    conn.autocommit = False
    try:
        with conn.cursor() as cur:
            # Resolve email → user_id
            cur.execute("SELECT user_id FROM users WHERE email = %s", (email,))
            row = cur.fetchone()
            if row is None:
                return False

            hashed = _ph.hash(new_password)
            cur.execute("""
                UPDATE users_confidential SET password = %s
                WHERE user_id = %s
            """, (hashed, row[0]))
            conn.commit()
            return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


# ── VECTOR / RAG QUERIES — do not modify ─────────────────────────────────────

def query_policy_vector_search(embedding: list[float], top_k: int = VECTOR_TOP_K) -> list[dict]:
    """
    Find the most relevant policy documents for a given query embedding.

    Args:
        embedding: Query vector from llm.embed(user_question)
        top_k:     Number of results to return

    Returns:
        List of dicts with title, category, content, and similarity score
    """
    sql = """
        SELECT
            title,
            category,
            content,
            1 - (embedding <=> %s::vector) AS similarity
        FROM policy_documents
        WHERE 1 - (embedding <=> %s::vector) > %s
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (vec_str, vec_str, VECTOR_SIMILARITY_THRESHOLD, vec_str, top_k))
            return [dict(row) for row in cur.fetchall()]


def store_policy_document(
    title: str,
    category: str,
    content: str,
    embedding: list[float],
    source_file: str = "",
) -> int:
    """
    Insert a policy document with its embedding into the database.
    Used by skeleton/seed_vectors.py — students don't need to call this directly.

    Returns:
        The new document's id
    """
    sql = """
        INSERT INTO policy_documents (title, category, content, embedding, source_file)
        VALUES (%s, %s, %s, %s::vector, %s)
        RETURNING id
    """
    vec_str = "[" + ",".join(str(x) for x in embedding) + "]"
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (title, category, content, vec_str, source_file))
            return cur.fetchone()[0]

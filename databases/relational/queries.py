"""
TransitFlow — Relational Database Queries

# TASK 6 EXTENSION:
# This file integrates the Task 6 Lost Items and Penalties database query functions.

This module handles all communication with PostgreSQL.

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
"""

# =========================================================================
# [ Architect Note: Concept Origination & Refinement ]
# The database queries of transaction operations, penalties and state machine updates 
# within this module were extensively modified and implemented by 
# Lucas (10LJN09) in this final version.
# =========================================================================

from __future__ import annotations

import json
import random
import string
from datetime import datetime, timezone
from typing import Optional

import psycopg2
import psycopg2.extras

from skeleton.config import PG_DSN, VECTOR_TOP_K, VECTOR_SIMILARITY_THRESHOLD


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

# TODO: Implement the query_ and execute_ functions below.
# ─────────────────────────────────────────────────────────────────────────────


# ── NATIONAL RAIL AVAILABILITY ────────────────────────────────────────────────

def query_national_rail_availability(
    origin_id: str,
    destination_id: str,
    travel_date: Optional[str] = None,
) -> list[dict]:
    """
    Return national rail schedules that serve both origin and destination stations
    in the correct order, along with seat occupancy for the requested travel date.

    This function filters schedules so that the origin stop appears before the
    destination stop and excludes passed-through stops at both ends. When a
    travel_date is supplied, it also counts confirmed/completed bookings on that
    schedule for that date and subtracts them from total seat capacity.

    Args:
        origin_id:       e.g. "NR01"
        destination_id:  e.g. "NR05"
        travel_date:     e.g. "2025-06-01" — if provided, only bookings on this
                         date are counted for availability calculation.

    Returns:
        A list of dictionaries containing schedule metadata and computed
        availability values such as schedule_id, line, service_type,
        departure_time, total_seats, and available_seats.
    """
    sql = """
        WITH seat_counts AS (
            SELECT 
                sl.schedule_id, 
                COUNT(s.seat_id) AS total_seats
            FROM national_rail_seat_layouts sl
            JOIN national_rail_coaches c ON sl.layout_id = c.layout_id
            JOIN national_rail_seats s ON c.coach_id = s.coach_id
            GROUP BY sl.schedule_id
        )
        SELECT 
            sch.schedule_id,
            sch.line,
            sch.service_type,
            (sch.first_train_time + (os.travel_time_from_origin_min * interval '1 minute'))::time AS departure_time,
            COALESCE(sc.total_seats, 0) AS total_seats
    """
    
    params = []
    
    if travel_date:
        sql += """
            , COALESCE((
                SELECT COUNT(booking_id)
                FROM national_rail_bookings b
                WHERE b.schedule_id = sch.schedule_id
                  AND b.status IN ('completed', 'confirmed')
                  AND b.travel_date = %s
            ), 0) AS booked_seats
        """
        params.append(travel_date)
    else:
        sql += """
            , 0 AS booked_seats
        """
        
    sql += """
        FROM national_rail_schedules sch
        JOIN national_rail_schedule_stops os ON sch.schedule_id = os.schedule_id
        JOIN national_rail_schedule_stops ds ON sch.schedule_id = ds.schedule_id
        LEFT JOIN seat_counts sc ON sch.schedule_id = sc.schedule_id
        WHERE os.station_id = %s
          AND ds.station_id = %s
          AND os.stop_order < ds.stop_order
          AND os.is_passed_through = false
          AND ds.is_passed_through = false
        ORDER BY departure_time ASC;
    """
    
    params.extend([origin_id, destination_id])

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            rows = cur.fetchall()
            
            results = []
            for row in rows:
                row_dict = dict(row)
                
                if 'departure_time' in row_dict and row_dict['departure_time'] is not None:
                    row_dict['departure_time'] = str(row_dict['departure_time'])
                
                total_seats = row_dict.get('total_seats', 0)
                booked_seats = row_dict.pop('booked_seats', 0)
                
                row_dict['available_seats'] = max(0, total_seats - booked_seats)
                results.append(row_dict)
                
            return results


def query_national_rail_fare(
    schedule_id: str,
    fare_class: str,
    stops_travelled: int,
) -> Optional[dict]:
    """
    Calculate the fare for a national rail journey.

    This function looks up schedule-specific pricing for the requested fare
    class and computes the total fare by adding the schedule's base fare to the
    per-stop rate multiplied by the requested number of stops.

    Args:
        schedule_id:     e.g. "NR_SCH01"
        fare_class:      "standard" or "first"
        stops_travelled: number of stops between origin and destination

    Returns:
        A dictionary with fare_class, base_fare_usd, per_stop_rate_usd, and
        total_fare_usd. Returns None when the schedule or fare class is not
        available.
    """
    sql = """
        SELECT 
            fare_class,
            base_fare_usd,
            per_stop_rate_usd,
            (base_fare_usd + (per_stop_rate_usd * %s)) AS total_fare_usd
        FROM national_rail_fares
        WHERE schedule_id = %s
          AND fare_class = %s;
    """
    
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (stops_travelled, schedule_id, fare_class))
            row = cur.fetchone()
            
            return dict(row) if row else None


# ── METRO SCHEDULES & FARE ────────────────────────────────────────────────────

def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:
    """
    Return metro schedules that connect the requested origin and destination.

    This query returns only schedules where the origin stop occurs before the
    destination stop in the service order. Each returned record includes the
    computed number of stops, the estimated travel duration, and the total fare
    for the selected route.

    Args:
        origin_id:       e.g. "MS01"
        destination_id:  e.g. "MS09"

    Returns:
        A list of dictionaries containing schedule metadata and computed travel
        details for the requested stop pair.
    """
    sql = """
        SELECT 
            sch.schedule_id,
            sch.line,
            sch.direction,
            sch.frequency_min,
            sch.first_train_time,
            sch.last_train_time,
            (dest_stop.stop_order - origin_stop.stop_order) AS stops_travelled,
            (sch.base_fare_usd + (sch.per_stop_rate_usd * (dest_stop.stop_order - origin_stop.stop_order))) AS total_fare_usd,
            (dest_stop.travel_time_from_origin_min - origin_stop.travel_time_from_origin_min) AS estimated_time_min
        FROM metro_schedules sch
        JOIN metro_schedule_stops origin_stop ON sch.schedule_id = origin_stop.schedule_id
        JOIN metro_schedule_stops dest_stop ON sch.schedule_id = dest_stop.schedule_id
        WHERE origin_stop.station_id = %s
          AND dest_stop.station_id = %s
          AND origin_stop.stop_order < dest_stop.stop_order
        ORDER BY sch.line, sch.direction;
    """
    
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (origin_id, destination_id))
            rows = cur.fetchall()
            
            results = []
            for row in rows:
                row_dict = dict(row)
                
                if 'first_train_time' in row_dict and row_dict['first_train_time'] is not None:
                    row_dict['first_train_time'] = str(row_dict['first_train_time'])
                if 'last_train_time' in row_dict and row_dict['last_train_time'] is not None:
                    row_dict['last_train_time'] = str(row_dict['last_train_time'])
                    
                results.append(row_dict)
                
            return results


def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]:
    """
    Calculate the metro fare for a single-ticket journey.

    This helper reads the schedule's base fare and per-stop rate, then
    computes the total amount for the requested stop count. It is intended for
    fare estimation and payment preparation.

    Args:
        schedule_id:     e.g. "MS_SCH01"
        stops_travelled: number of stops between origin and destination

    Returns:
        A dictionary with base_fare_usd, per_stop_rate_usd, and total_fare_usd.
        Returns None when the schedule_id is not found.
    """
    sql = """
        SELECT 
            base_fare_usd,
            per_stop_rate_usd,
            (base_fare_usd + (per_stop_rate_usd * %s)) AS total_fare_usd
        FROM metro_schedules
        WHERE schedule_id = %s;
    """
    
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (stops_travelled, schedule_id))
            row = cur.fetchone()
            
            return dict(row) if row else None


# ── SEAT SELECTION ────────────────────────────────────────────────────────────

def query_available_seats(
    schedule_id: str,
    travel_date: str,
    fare_class: str,
) -> list[dict]:
    """
    Return available seats for a national rail journey on a specific travel date.

    This query inspects the seat layout for the requested schedule and fare
    class, then removes seats that are already reserved in confirmed or
    completed bookings for the same travel date. The results are sorted by
    coach, row, and column for consistent seat selection.

    Args:
        schedule_id:  e.g. "NR_SCH01"
        travel_date:  e.g. "2025-06-01"
        fare_class:   "standard" or "first"

    Returns:
        A list of dictionaries containing seat_id, coach, row, and column.
    """
    sql = """
        SELECT DISTINCT
            s.seat_id,
            c.coach_name AS coach,
            s.row_num AS row,
            s.column_letter AS column
        FROM national_rail_seats s
        JOIN national_rail_coaches c ON s.coach_id = c.coach_id
        JOIN national_rail_seat_layouts l ON c.layout_id = l.layout_id
        WHERE l.schedule_id = %s 
          AND c.fare_class = %s
          AND NOT EXISTS (
              SELECT 1 
              FROM national_rail_bookings b
              WHERE b.schedule_id = %s
                AND b.travel_date = %s
                AND b.coach = c.coach_name
                AND b.seat_id = s.seat_id
                AND b.status IN ('confirmed', 'completed')
          )
        ORDER BY c.coach_name, s.row_num, s.column_letter;
    """
    
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (schedule_id, fare_class, schedule_id, travel_date))
            rows = cur.fetchall()
            return [dict(row) for row in rows]


def auto_select_adjacent_seats(available_seats: list[dict], count: int) -> list[str]:
    """
    Select `count` seats that are as close together as possible.

    The ordering logic first searches for enough seats within a single row.
    If no row has enough contiguous seats, it falls back to the natural
    row-and-column ordering of all available seats, which effectively selects a
    compact group.

    Args:
        available_seats: result of query_available_seats()
        count:           number of seats required

    Returns:
        A list of selected seat_id values.
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
    """
    Return a user's active profile by email.

    Only users with `is_active = true` are returned. This helper is used by
    account screens and wallet views, and it intentionally omits any
    credentials or confidential fields.

    Returns:
        A dictionary containing public user profile fields, or None if not found.
    """
    sql = """
        SELECT 
            user_id,
            full_name,
            full_name AS name,
            email,
            phone,
            date_of_birth,
            EXTRACT(YEAR FROM date_of_birth) AS year_of_birth,
            registered_at,
            verified_concession,
            app_credit_balance
        FROM users
        WHERE email = %s 
          AND is_active = true;
    """
    
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (user_email,))
            row = cur.fetchone()
            return dict(row) if row else None


def query_user_bookings(user_email: str) -> dict:
    """
    Return a user's combined booking history for national rail and metro.

    The function performs separate queries for each transport network and
    normalizes datetime-like fields to strings so that the returned payload is
    easier to serialize in frontend and API responses.

    Returns:
        A dictionary with keys 'national_rail' and 'metro', each containing a
        list of history records sorted by purchase/booked time.
    """
    sql_rail = """
        SELECT 
            b.booking_id,
            b.schedule_id,
            b.origin_station_id,
            b.destination_station_id,
            b.travel_date,
            b.departure_time,
            b.ticket_type,
            b.passenger_type,
            b.fare_class,
            b.coach,
            b.seat_id,
            b.amount_usd,
            b.status,
            b.booked_at,
            b.travelled_at
        FROM national_rail_bookings b
        JOIN users u ON b.user_id = u.user_id
        WHERE u.email = %s
        ORDER BY b.booked_at DESC;
    """

    sql_metro = """
        SELECT 
            m.trip_id,
            m.schedule_id,
            m.origin_station_id,
            m.destination_station_id,
            m.travel_date,
            m.ticket_type,
            m.passenger_type,
            m.amount_usd,
            m.status,
            m.purchased_at,
            m.travelled_at
        FROM metro_travel_history m
        JOIN users u ON m.user_id = u.user_id
        WHERE u.email = %s
        ORDER BY m.purchased_at DESC;
    """
    
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            
            # 1. Query National Rail booking history
            cur.execute(sql_rail, (user_email,))
            rail_rows = cur.fetchall()
            
            rail_list = []
            for row in rail_rows:
                row_dict = dict(row)
                for time_field in ['travel_date', 'departure_time', 'booked_at', 'travelled_at']:
                    if time_field in row_dict and row_dict[time_field] is not None:
                        row_dict[time_field] = str(row_dict[time_field])
                rail_list.append(row_dict)
                
            # 2. Query Metro trip history
            cur.execute(sql_metro, (user_email,))
            metro_rows = cur.fetchall()
            
            metro_list = []
            for row in metro_rows:
                row_dict = dict(row)
                for time_field in ['travel_date', 'purchased_at', 'travelled_at']:
                    if time_field in row_dict and row_dict[time_field] is not None:
                        row_dict[time_field] = str(row_dict[time_field])
                metro_list.append(row_dict)
                
            return {
                "national_rail": rail_list,
                "metro": metro_list
            }


def query_payment_info(booking_id: str) -> Optional[dict]:
    """
    Return the payment record associated with a booking or metro trip.

    This helper fetches payment metadata including payment method, status, and
    paid_at timestamp. It is useful for confirming completed payments and
    showing payment details in customer service or booking summary views.

    Returns:
        A dictionary containing payment details, or None if no payment record
        exists for the given booking_id.
    """
    sql = """
        SELECT 
            payment_id,
            booking_id,
            amount_usd,
            amount_usd AS amount,
            method,
            method AS payment_method,
            status,
            paid_at
        FROM payments
        WHERE booking_id = %s;
    """
    
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (booking_id,))
            row = cur.fetchone()
            
            if row:
                row_dict = dict(row)
                if 'paid_at' in row_dict and row_dict['paid_at'] is not None:
                    row_dict['paid_at'] = str(row_dict['paid_at'])
                return row_dict
                
            return None


def query_linked_trip_details(linked_trip_id: str) -> Optional[dict]:
    """
    [LJN Temp] Polymorphic Association Helper.
    Fetches the details of a previous trip, which could be either a National Rail booking
    or a Metro travel history record, based on the ID prefix.
    """
    if not linked_trip_id:
        return None

    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if linked_trip_id.startswith('BK'):
                cur.execute("SELECT * FROM national_rail_bookings WHERE booking_id = %s", (linked_trip_id,))
                row = cur.fetchone()
                if row:
                    return dict(row)
            elif linked_trip_id.startswith('MT'):
                cur.execute("SELECT * FROM metro_travel_history WHERE trip_id = %s", (linked_trip_id,))
                row = cur.fetchone()
                if row:
                    return dict(row)
            return None


# ── TRANSACTIONAL OPERATIONS ──────────────────────────────────────────────────

def execute_wallet_deduction(user_id: str, amount_usd: float) -> tuple[bool, str]:
    """
    [LJN Temp] Safely deduct from a user's wallet using Pessimistic Locking.
    Prevents race conditions (Lost Update problem) if the user attempts to pay from multiple devices simultaneously.
    """
    if amount_usd <= 0:
        return False, "Amount to deduct must be positive."

    conn = _connect()
    # Disable autocommit to start a transaction explicitly
    conn.autocommit = False 
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Lock the row exclusively for this transaction
            cur.execute("SELECT app_credit_balance FROM users WHERE user_id = %s FOR UPDATE", (user_id,))
            row = cur.fetchone()
            
            if not row:
                conn.rollback()
                return False, "User not found."
                
            current_balance = float(row['app_credit_balance'])
            
            # 2. Check if sufficient balance
            if current_balance < amount_usd:
                conn.rollback()
                return False, "Insufficient wallet balance."
                
            # 3. Deduct the amount
            cur.execute(
                "UPDATE users SET app_credit_balance = app_credit_balance - %s WHERE user_id = %s",
                (amount_usd, user_id)
            )
            
            # 4. Commit the transaction (releases the lock)
            conn.commit()
            return True, "Payment successful."
    except Exception as e:
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        conn.close()


def execute_booking(
    user_id: str,
    schedule_id: str,
    origin_station_id: str,
    destination_station_id: str,
    travel_date: str,
    fare_class: str,
    seat_id: str,
    ticket_type: str = "single",
    passenger_type: str = "adult",
    linked_trip_id: str = None,
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
        passenger_type:         "adult", "senior", or "disabled"
        linked_trip_id:         Optional trip ID for interchange.

    Returns:
        (True, booking_dict)   on success
        (False, error_message) on failure
        
    IMPLEMENTATION NOTE FOR STUDENTS (LJN Temp Decisions):
    1. Wallet Deduction (Race Condition Prevention):
       Must use pessimistic locking `SELECT app_credit_balance FROM users WHERE user_id = %s FOR UPDATE` 
       before checking balance and deducting, to prevent concurrent double-spending.
    2. Polymorphic Association for Interchange:
       If a linked_trip_id is provided, check its prefix in Python.
       If `linked_trip_id.startswith('BK')`: query national_rail_bookings. 
       If `linked_trip_id.startswith('MT')`: query metro_travel_history.
       This avoids rigid SQL foreign keys and enables cross-network interchange tracking.
    """
    from datetime import datetime, timezone
    
    conn = _connect()
    conn.autocommit = False

    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Fetch Schedule Info (departure_time, stops_travelled)
            schedule_sql = """
                SELECT 
                    (sch.first_train_time + (os.travel_time_from_origin_min * interval '1 minute'))::time AS departure_time,
                    (ds.stop_order - os.stop_order) AS stops_travelled
                FROM national_rail_schedules sch
                JOIN national_rail_schedule_stops os ON sch.schedule_id = os.schedule_id
                JOIN national_rail_schedule_stops ds ON sch.schedule_id = ds.schedule_id
                WHERE sch.schedule_id = %s
                  AND os.station_id = %s
                  AND ds.station_id = %s
                  AND os.stop_order < ds.stop_order
                  AND os.is_passed_through = false
                  AND ds.is_passed_through = false;
            """
            cur.execute(schedule_sql, (schedule_id, origin_station_id, destination_station_id))
            schedule_info = cur.fetchone()
            if not schedule_info:
                conn.rollback()
                return False, "Invalid schedule or stations."
            
            departure_time = schedule_info["departure_time"]
            stops_travelled = schedule_info["stops_travelled"]

            # 2. Fetch Fare Info
            fare_sql = """
                SELECT base_fare_usd, per_stop_rate_usd
                FROM national_rail_fares
                WHERE schedule_id = %s AND fare_class = %s
            """
            cur.execute(fare_sql, (schedule_id, fare_class))
            fare_info = cur.fetchone()
            if not fare_info:
                conn.rollback()
                return False, f"Fare class '{fare_class}' not found for this schedule."
            
            amount_usd = float(fare_info["base_fare_usd"] + (stops_travelled * fare_info["per_stop_rate_usd"]))

            # 3. Row-level Lock Seat
            if seat_id.lower() == "any":
                seat_sql = """
                    SELECT s.seat_id, c.coach_name
                    FROM national_rail_seats s
                    JOIN national_rail_coaches c ON s.coach_id = c.coach_id
                    JOIN national_rail_seat_layouts l ON c.layout_id = l.layout_id
                    WHERE l.schedule_id = %s
                      AND c.fare_class = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM national_rail_bookings b
                          WHERE b.schedule_id = %s
                            AND b.travel_date = %s
                            AND b.coach = c.coach_name
                            AND b.seat_id = s.seat_id
                            AND b.status IN ('confirmed', 'completed')
                      )
                    ORDER BY c.coach_name, s.row_num, s.column_letter
                    FOR UPDATE OF s SKIP LOCKED
                    LIMIT 1;
                """
                cur.execute(seat_sql, (schedule_id, fare_class, schedule_id, travel_date))
            else:
                seat_sql = """
                    SELECT s.seat_id, c.coach_name
                    FROM national_rail_seats s
                    JOIN national_rail_coaches c ON s.coach_id = c.coach_id
                    JOIN national_rail_seat_layouts l ON c.layout_id = l.layout_id
                    WHERE l.schedule_id = %s
                      AND c.fare_class = %s
                      AND s.seat_id = %s
                      AND NOT EXISTS (
                          SELECT 1 FROM national_rail_bookings b
                          WHERE b.schedule_id = %s
                            AND b.travel_date = %s
                            AND b.coach = c.coach_name
                            AND b.seat_id = s.seat_id
                            AND b.status IN ('confirmed', 'completed')
                      )
                    FOR UPDATE OF s SKIP LOCKED
                    LIMIT 1;
                """
                cur.execute(seat_sql, (schedule_id, fare_class, seat_id, schedule_id, travel_date))
                
            seat_info = cur.fetchone()
            if not seat_info:
                conn.rollback()
                return False, "Seat unavailable or already booked."
            
            final_seat_id = seat_info["seat_id"]
            final_coach = seat_info["coach_name"]

            # 4. Lock User Wallet & Deduct
            wallet_sql = """
                SELECT app_credit_balance, verified_concession
                FROM users
                WHERE user_id = %s
                FOR UPDATE;
            """
            cur.execute(wallet_sql, (user_id,))
            user_info = cur.fetchone()
            if not user_info:
                conn.rollback()
                return False, "User not found."
            
            app_credit_balance = float(user_info["app_credit_balance"])
            if app_credit_balance < amount_usd:
                conn.rollback()
                return False, f"Insufficient app credit. Required: ${amount_usd:.2f}, Available: ${app_credit_balance:.2f}"
            
            update_wallet_sql = """
                UPDATE users
                SET app_credit_balance = app_credit_balance - %s
                WHERE user_id = %s
            """
            cur.execute(update_wallet_sql, (amount_usd, user_id))

            # 5. Concession Verification Logic
            verified_concession = user_info["verified_concession"]
            concession_status = "not_required"
            if passenger_type in ["senior", "disabled"]:
                if verified_concession == passenger_type:
                    concession_status = "verified_at_gate"
                else:
                    concession_status = "pending_gate_check"

            # 6. Insert Booking and Payment
            booking_id = _gen_booking_id()
            insert_booking_sql = """
                INSERT INTO national_rail_bookings (
                    booking_id, user_id, schedule_id, origin_station_id, destination_station_id,
                    travel_date, departure_time, ticket_type, passenger_type, linked_trip_id, 
                    fare_class, coach, seat_id, concession_verification_status, stops_travelled, 
                    amount_usd, status, booked_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, 
                    %s, %s, %s, %s, %s, 
                    %s, 'confirmed', %s
                )
            """
            booked_at = datetime.now(timezone.utc)
            cur.execute(insert_booking_sql, (
                booking_id, user_id, schedule_id, origin_station_id, destination_station_id,
                travel_date, departure_time, ticket_type, passenger_type, linked_trip_id,
                fare_class, final_coach, final_seat_id, concession_status, stops_travelled, 
                amount_usd, booked_at
            ))

            payment_id = _gen_payment_id()
            insert_payment_sql = """
                INSERT INTO payments (payment_id, booking_id, amount_usd, method, status, paid_at)
                VALUES (%s, %s, %s, 'app_credit', 'paid', %s)
            """
            cur.execute(insert_payment_sql, (payment_id, booking_id, amount_usd, booked_at))

            conn.commit()
            
            booking_dict = {
                "booking_id": booking_id,
                "user_id": user_id,
                "schedule_id": schedule_id,
                "origin_station_id": origin_station_id,
                "destination_station_id": destination_station_id,
                "travel_date": travel_date,
                "departure_time": str(departure_time),
                "fare_class": fare_class,
                "coach": final_coach,
                "seat_id": final_seat_id,
                "amount_usd": amount_usd,
                "status": "confirmed"
            }
            return True, booking_dict

    except Exception as e:
        conn.rollback()
        return False, f"Booking execution failed: {str(e)}"
    finally:
        conn.close()


def execute_cancellation(booking_id: str, user_id: str) -> tuple[bool, dict | str]:
    """
    Cancel a national rail booking owned by the given user.

    This function performs ownership and status validation, checks the
    departure window relative to the current time, applies the refund policy,
    and uses a transaction to commit both the cancellation and any wallet
    refund together.

    Refund rules:
      - Normal service: RF001 windows (100% / 75% / 50% / 0%)
      - Express service: RF002 windows (100% / 50% / 0%)

    Args:
        booking_id: e.g. "BK001"
        user_id:    must match the booking's user_id

    Returns:
        (True, result_dict) with refund_amount_usd and policy_note, or
        (False, error_message) when cancellation is not permitted.
    """
    conn = _connect()
    conn.autocommit = False # Disable autocommit to start an explicit transaction
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # 1. Retrieve booking and schedule information (use FOR UPDATE to
            #    lock the booking row and prevent race conditions)
            select_sql = """
                SELECT 
                    b.user_id,
                    b.status,
                    b.amount_usd,
                    b.travel_date,
                    b.departure_time,
                    s.service_type
                FROM national_rail_bookings b
                JOIN national_rail_schedules s ON b.schedule_id = s.schedule_id
                WHERE b.booking_id = %s
                FOR UPDATE OF b;
            """
            cur.execute(select_sql, (booking_id,))
            row = cur.fetchone()
            
            # 2. Basic validation and authorization checks
            if not row:
                conn.rollback()
                return False, "Booking not found."
                
            if row['user_id'] != user_id:
                conn.rollback()
                return False, "Unauthorized: You do not own this booking."
                
            if row['status'] == 'cancelled':
                conn.rollback()
                return False, "Booking is already cancelled."
                
            # 3. Compute departure datetime and time difference from now
            from datetime import datetime
            dt_departure = datetime.combine(row['travel_date'], row['departure_time'])
            
            # Decide whether the DB datetime has timezone info; choose an
            # appropriate `now` to compute the difference.
            if dt_departure.tzinfo is None:
                now = datetime.now()
            else:
                now = datetime.now(dt_departure.tzinfo)
                
            time_diff = dt_departure - now
            hours_before = time_diff.total_seconds() / 3600
            
            if hours_before <= 0:
                conn.rollback()
                return False, "Cannot cancel: Train has already departed."
                
            # 4. Calculate refund according to service_type and hours_before
            service_type = str(row['service_type']).lower()
            amount = float(row['amount_usd'])
            refund_amount = 0.0
            policy_note = ""
            
            if "express" in service_type:
                # RF002 Express Service
                if hours_before >= 48:
                    refund_amount = amount * 1.0
                    policy_note = "RF002: >= 48h before departure (100% refund)"
                elif hours_before >= 24:
                    refund_amount = amount * 0.5
                    policy_note = "RF002: 24h-48h before departure (50% refund)"
                else:
                    refund_amount = 0.0
                    policy_note = "RF002: < 24h before departure (0% refund)"
            else:
                # RF001 Normal Service
                if hours_before >= 24:
                    refund_amount = amount * 1.0
                    policy_note = "RF001: >= 24h before departure (100% refund)"
                elif hours_before >= 12:
                    refund_amount = amount * 0.75
                    policy_note = "RF001: 12h-24h before departure (75% refund)"
                elif hours_before >= 2:
                    refund_amount = amount * 0.5
                    policy_note = "RF001: 2h-12h before departure (50% refund)"
                else:
                    refund_amount = 0.0
                    policy_note = "RF001: < 2h before departure (0% refund)"
                    
            refund_amount = round(refund_amount, 2)
            
            # 5. Persist changes to the database
            # 5.1 Mark the booking as cancelled
            update_booking_sql = "UPDATE national_rail_bookings SET status = 'cancelled' WHERE booking_id = %s"
            cur.execute(update_booking_sql, (booking_id,))
            
            # 5.2 If there is a refund, credit the user's wallet
            if refund_amount > 0:
                update_user_sql = "UPDATE users SET app_credit_balance = app_credit_balance + %s WHERE user_id = %s"
                cur.execute(update_user_sql, (refund_amount, user_id))
                
            # 6. Commit the transaction to finalize the cancellation and refund
            conn.commit()
            
            return True, {
                "refund_amount": refund_amount,
                "refund_amount_usd": refund_amount,
                "policy_note": policy_note
            }
            
    except Exception as e:
        # On unexpected error, rollback to avoid partial updates
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        # Ensure the DB connection is closed and resources are released
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
    Register a new user and create both public and confidential profile records.

    The function stores non-sensitive profile data in `users`, while secrets
    such as the password hash, secret question, and secret answer are stored in
    `users_confidential`. It also seeds the new account with a demo wallet
    balance to enable transaction flows during testing.

    Returns:
        (True, user_id) on success, or (False, error_message) on failure.

    Note:
        Password hashing is performed using Argon2, which securely stores a
        salted hash instead of the plaintext password.
    """
    import uuid
    from datetime import datetime, timezone
    import psycopg2.errors
    from argon2 import PasswordHasher
    
        # 1. Preprocessing and data preparation
        # Architectural Note:
        # Use a truncated UUID4 to reduce the probability of primary key collisions
        # under concurrent registrations. The `U-` prefix yields a human-friendly
        # business key (e.g. U-A1B2C3D4) useful for routing and debugging.
    user_id = f"U-{uuid.uuid4().hex[:8].upper()}"
    full_name = f"{first_name} {surname}"
    date_of_birth = f"{year_of_birth}-01-01"
    registered_at = datetime.now(timezone.utc)
    
    # 2. High-strength password hashing (Argon2id)
    # Always store only a salted hash (argon2) rather than plaintext passwords.
    ph = PasswordHasher()
    hashed_password = ph.hash(password)
    # Hash the secret answer as well, normalized to lowercase
    hashed_secret_answer = ph.hash(secret_answer.strip().lower())
    
    conn = _connect()
    conn.autocommit = False # Disable autocommit to ensure the registration is atomic
    
    try:
        with conn.cursor() as cur:
            # 3. Insert public user profile into `users` and seed test wallet
            #    with a demo balance (1000.00). This table stores non-sensitive
            #    profile attributes that can be exposed to other services.
            insert_users_sql = """
                INSERT INTO users (user_id, full_name, email, date_of_birth, registered_at, app_credit_balance)
                VALUES (%s, %s, %s, %s, %s, 1000.00)
            """
            cur.execute(insert_users_sql, (user_id, full_name, email, date_of_birth, registered_at))
            
            # 4. Insert confidential credentials into `users_confidential`.
            #    This table stores secrets (password hash, secret question/answer)
            #    that must never be returned in API responses.
            insert_confidential_sql = """
                INSERT INTO users_confidential (user_id, password, secret_question, secret_answer)
                VALUES (%s, %s, %s, %s)
            """
            cur.execute(insert_confidential_sql, (user_id, hashed_password, secret_question, hashed_secret_answer))
            
            # 5. Commit when both inserts succeed to ensure consistency.
            conn.commit()
            return True, user_id
            
    except psycopg2.errors.UniqueViolation:
        # Handle UNIQUE constraint violation for email (already registered).
        conn.rollback()
        return False, "Email already registered."
    except Exception as e:
        # Handle unexpected database errors and rollback to keep DB consistent.
        conn.rollback()
        return False, f"Database error: {str(e)}"
    finally:
        # Ensure the connection is closed and resources are released.
        conn.close()


def login_user(email: str, password: str) -> Optional[dict]:
    """
    Authenticate a user by email and password.

    This function verifies the supplied password against the stored Argon2 hash.
    On success, it returns a sanitized user dictionary with the password hash
    removed and the user's name split into first_name and surname.

    Returns:
        A dictionary containing public user profile fields on success, or None
        when authentication fails.
    """
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError
    
    sql = """
        SELECT 
            u.user_id, 
            u.email, 
            u.full_name, 
            u.phone, 
            u.date_of_birth, 
            u.is_active,
            uc.password AS hashed_password
        FROM users u
        JOIN users_confidential uc ON u.user_id = uc.user_id
        WHERE u.email = %s;
    """
    
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()

            # If email is not found, return None to avoid user enumeration
            if not row:
                return None

            # 1. Verify password using Argon2 (hash encodes salt and parameters)
            ph = PasswordHasher()
            try:
                ph.verify(row['hashed_password'], password)
            except VerifyMismatchError:
                # Password mismatch: deny access
                return None

            # 2. Prepare the user dictionary to return
            user_dict = dict(row)

            # SECURITY: remove password hash before returning any data
            del user_dict['hashed_password']

            # Split full_name into first_name and surname for convenience
            full_name = user_dict.get('full_name', '')
            parts = full_name.split(' ', 1)
            user_dict['first_name'] = parts[0] if len(parts) > 0 else ''
            user_dict['surname'] = parts[1] if len(parts) > 1 else ''

            # Normalize date_of_birth to a string for JSON serialization
            if user_dict.get('date_of_birth'):
                user_dict['date_of_birth'] = str(user_dict['date_of_birth'])
            else:
                user_dict['date_of_birth'] = None

            return user_dict


def get_user_secret_question(email: str) -> Optional[str]:
    """
    Return the secret question associated with a registered email.

    This helper supports account recovery flows by allowing the application to
    prompt the user with their registered security question.

    Returns:
        The secret question string, or None if the email is not registered.
    """
    sql = """
        SELECT uc.secret_question 
        FROM users u 
        JOIN users_confidential uc ON u.user_id = uc.user_id 
        WHERE u.email = %s;
    """
    
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
            
            # If the email is not found, return None
            if not row:
                return None

            return row['secret_question']


def verify_secret_answer(email: str, answer: str) -> bool:
    """
    Verify whether the supplied secret answer matches the stored answer.

    The comparison is case-insensitive and trims whitespace from both values.
    This is intended to tolerate common formatting differences while still
    validating the user's knowledge of their registered secret answer.

    Returns:
        True when the normalized answers match, otherwise False.
    """
    # Guard clause: if the provided answer is empty, reject verification
    if not answer:
        return False
        
    sql = """
        SELECT uc.secret_answer 
        FROM users u 
        JOIN users_confidential uc ON u.user_id = uc.user_id 
        WHERE u.email = %s;
    """
    
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (email,))
            row = cur.fetchone()
            
            # If the email is not found, return False
            if not row:
                return False

            stored_answer = row['secret_answer']

            # If the stored answer is missing, reject verification
            if not stored_answer:
                return False

            from argon2 import PasswordHasher
            from argon2.exceptions import VerifyMismatchError
            
            ph = PasswordHasher()
            try:
                # Verify the provided answer against the stored hash
                ph.verify(stored_answer, answer.strip().lower())
                return True
            except VerifyMismatchError:
                return False


def update_password(email: str, new_password: str) -> bool:
    """
    Update a user's password by hashing the new value and storing it securely.

    This helper replaces the existing password hash in the confidential table.
    It uses a transaction to ensure the update either commits or rolls back as a
    unit.

    Returns:
        True when the password was updated successfully, otherwise False.
    """
    from argon2 import PasswordHasher
    
    # 1. Hash the new password using Argon2 to ensure safe storage
    ph = PasswordHasher()
    hashed_password = ph.hash(new_password)

    # 2. Prepare SQL that updates the confidential table for the user
    #    using a subquery to map email -> user_id inside the database engine.
    sql = """
        UPDATE users_confidential 
        SET password = %s 
        WHERE user_id = (SELECT user_id FROM users WHERE email = %s);
    """
    
    conn = _connect()
    conn.autocommit = False # Disable autocommit to protect the write in a transaction
    
    try:
        with conn.cursor() as cur:
            cur.execute(sql, (hashed_password, email))

            # 3. Check whether any row was updated; if not, the email likely doesn't exist
            if cur.rowcount > 0:
                conn.commit()
                return True
            else:
                # No matching email -> no update performed
                conn.rollback()
                return False

    except Exception:
        # On unexpected errors, rollback to keep DB consistent
        conn.rollback()
        return False

    finally:
        # Always close the connection and release resources
        conn.close()


# ── LOST ITEMS & PENALTIES ────────────────────────────────────────────────────

# TASK 6 EXTENSION:
# Query Lost Items (with optional filters)
# RATIONALE: We allow filtering by station_id and status because station staff need to 
# query items located specifically at their station, while the system needs to filter out 'claimed' items.
def query_lost_items(station_id: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
    """Retrieve lost items, optionally filtered by station or status."""
    sql = "SELECT * FROM lost_items WHERE 1=1"
    params = []
    if station_id:
        sql += " AND station_id = %s"
        params.append(station_id)
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY found_date DESC"
    
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, tuple(params))
            return [dict(row) for row in cur.fetchall()]


def execute_report_lost_item(
    item_id: str,
    station_id: str,
    category: str,
    description: str,
    is_high_value: bool = False
) -> tuple[bool, str]:
    """Insert a new lost item record."""
    sql = """
        INSERT INTO lost_items (
            item_id, reported_date, station_id, category, 
            description, is_high_value, status
        ) VALUES (%s, %s, %s, %s, %s, %s, 'reported')
    """
    now = datetime.now(timezone.utc)
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (item_id, now, station_id, category, description, is_high_value))
                return True, "Lost item reported successfully."
    except Exception as e:
        # RATIONALE: We explicitly return False in the except block to avoid a false positive.
        # This prevents the system from confirming a report when the database insertion actually failed.
        return False, f"Database error: {str(e)}"

# TASK 6 EXTENSION:
# Query User Penalties
# RATIONALE: We sort by violation_date DESC so that the user and agent always see 
# the most recent (and likely unpaid) fines first, preventing overdue penalties from being missed.
def query_user_penalties(user_id: str) -> list[dict]:
    """Retrieve all penalties for a given user."""
    sql = "SELECT * FROM penalties WHERE user_id = %s ORDER BY violation_date DESC"
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, (user_id,))
            return [dict(row) for row in cur.fetchall()]


def execute_issue_penalty(      #可增加狀態更新--LJN
    penalty_id: str,
    user_id: str,
    violation_type: str,
    location: str,
    amount_usd: float,
    due_date: datetime
) -> tuple[bool, str]:
    """Issue a new penalty to a user."""
    sql = """
        INSERT INTO penalties (
            penalty_id, user_id, violation_type, violation_date, 
            location, amount_usd, status, due_date
        ) VALUES (%s, %s, %s, %s, %s, %s, 'unpaid', %s)
    """
    now = datetime.now(timezone.utc)
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (penalty_id, user_id, violation_type, now, location, amount_usd, due_date))
                return True, "Penalty issued successfully."
    except Exception as e:
        return False, f"Database error: {str(e)}"


def execute_update_lost_item_status(item_id: str, new_status: str, claimed_by_user: Optional[str] = None) -> tuple[bool, str]:
    """
    Update the status of a lost item (e.g., from 'reported' to 'found', or 'found' to 'claimed').
    If status is 'claimed', claimed_by_user must be provided.
    """
    now = datetime.now(timezone.utc)
    sql = "UPDATE lost_items SET status = %s"
    params = [new_status]
    
    if new_status == 'found':
        sql += ", found_date = COALESCE(found_date, %s)"
        params.append(now)
    elif new_status == 'claimed':
        if not claimed_by_user:
            return False, "claimed_by_user is required when status is 'claimed'"
        sql += ", claimed_date = %s, claimed_by_user = %s"
        params.extend([now, claimed_by_user])

    sql += " WHERE item_id = %s"
    params.append(item_id)

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, tuple(params))
                if cur.rowcount == 0:
                    return False, "Lost item not found."
                return True, "Lost item status updated successfully."
    except Exception as e:
        return False, f"Database error: {str(e)}"


# RATIONALE: We enforce that a penalty can only be marked 'paid' if its current status is 'unpaid'.
# This atomic check (AND status = 'unpaid') prevents race conditions where an appealed or already paid 
# penalty gets paid twice by accident.
def execute_pay_penalty(penalty_id: str) -> tuple[bool, str]:
    """
    Update a penalty status to 'paid' and set the paid_at timestamp.
    """
    now = datetime.now(timezone.utc)
    sql = "UPDATE penalties SET status = 'paid', paid_at = %s WHERE penalty_id = %s AND status = 'unpaid'"
    
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (now, penalty_id))
                if cur.rowcount == 0:
                    return False, "Penalty not found or already paid."
                return True, "Penalty paid successfully."
    except Exception as e:
        return False, f"Database error: {str(e)}"


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


def clear_policy_documents() -> None:
    """Clear all existing policy documents to prevent duplicates when reseeding."""
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE policy_documents RESTART IDENTITY;")
        conn.commit()


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
def query_lost_item(item_id: str) -> Optional[dict]:
    """
    Retrieve information about a specific lost item by its item_id.
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM lost_items WHERE item_id = %s;", (item_id,))
            row = cur.fetchone()
            return dict(row) if row else {"error": "Lost item not found."}

def query_user_penalties(user_id: str) -> list[dict]:
    """
    Retrieve all penalty records for a specific user.
    """
    with _connect() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT * FROM penalties WHERE user_id = %s;", (user_id,))
            return [dict(row) for row in cur.fetchall()]

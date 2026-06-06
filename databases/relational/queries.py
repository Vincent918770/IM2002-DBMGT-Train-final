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

    Args:
        origin_id:       e.g. "NR01"
        destination_id:  e.g. "NR05"
        travel_date:     e.g. "2025-06-01" — used to count bookings; omit for general info
    """
    raise NotImplementedError("TODO: implement after designing your schema")


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
    raise NotImplementedError("TODO: implement after designing your schema")


# ── METRO SCHEDULES & FARE ────────────────────────────────────────────────────

def query_metro_schedules(origin_id: str, destination_id: str) -> list[dict]:
    """
    Return metro schedules that serve both origin and destination in the correct order.

    Args:
        origin_id:       e.g. "MS01"
        destination_id:  e.g. "MS09"
    """
    raise NotImplementedError("TODO: implement after designing your schema")


def query_metro_fare(schedule_id: str, stops_travelled: int) -> Optional[dict]:
    """
    Calculate the metro fare for a single-ticket journey.

    Args:
        schedule_id:     e.g. "MS_SCH01"
        stops_travelled: number of stops between origin and destination

    Returns:
        dict with base_fare_usd, per_stop_rate_usd, total_fare_usd
    """
    raise NotImplementedError("TODO: implement after designing your schema")


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
    raise NotImplementedError("TODO: implement after designing your schema")


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
    raise NotImplementedError("TODO: implement after designing your schema")


def query_user_bookings(user_email: str) -> dict:
    """
    Return a user's combined booking history (national rail + metro).

    Returns:
        dict with keys 'national_rail' (list) and 'metro' (list)
    """
    raise NotImplementedError("TODO: implement after designing your schema")


def query_payment_info(booking_id: str) -> Optional[dict]:
    """Return payment record for a booking or metro trip."""
    raise NotImplementedError("TODO: implement after designing your schema")


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
    raise NotImplementedError("TODO: implement after designing your schema")


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
    raise NotImplementedError("TODO: implement after designing your schema")


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

    NOTE: passwords are stored as plain text here intentionally for teaching
    purposes. In production, replace with a salted hash (e.g. bcrypt).
    """
    raise NotImplementedError("TODO: implement after designing your schema")


def login_user(email: str, password: str) -> Optional[dict]:
    """
    Verify credentials. Returns a user dict on success or None on failure.
    Dict keys: user_id, email, full_name, first_name, surname, phone, date_of_birth, is_active.
    """
    raise NotImplementedError("TODO: implement after designing your schema")


def get_user_secret_question(email: str) -> Optional[str]:
    """Return the secret question for a registered email, or None if not found."""
    raise NotImplementedError("TODO: implement after designing your schema")


def verify_secret_answer(email: str, answer: str) -> bool:
    """Return True if the provided answer matches the stored secret answer (case-insensitive)."""
    raise NotImplementedError("TODO: implement after designing your schema")


def update_password(email: str, new_password: str) -> bool:
    """Update the password for a user. Returns True if the row was updated."""
    raise NotImplementedError("TODO: implement after designing your schema")


# ── LOST ITEMS & PENALTIES ────────────────────────────────────────────────────

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
        return False, f"Database error: {str(e)}"


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

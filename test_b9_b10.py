import sys
from datetime import datetime, date

sys.path.append('.')

from databases.relational.queries import (
    query_user_profile,
    query_user_bookings,
    query_payment_info,
    execute_booking,
    execute_cancellation
)

# Alice's app credit balance is 0! That's why it failed... wait, did it fail on seat or balance?
# Ah, it said "Seat unavailable or already booked." So it failed on the seat.
# Let's give Alice some money first so B9 succeeds.
from databases.relational.queries import _connect
with _connect() as conn:
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("UPDATE users SET app_credit_balance = 1000 WHERE user_id = 'RU01'")

print("\n=== B9: execute_booking ===")
ok, res = execute_booking(
    user_id="RU01",
    schedule_id="NR_SCH01",
    origin_station_id="NR01",
    destination_station_id="NR05",
    travel_date="2026-10-01",
    fare_class="standard",
    seat_id="any"
)
print("Result:", ok, res)

if ok:
    booked_seat_id = res['seat_id']
    print(f"\nTrying to book the SAME seat ({booked_seat_id}) again...")
    ok2, res2 = execute_booking(
        user_id="RU01",
        schedule_id="NR_SCH01",
        origin_station_id="NR01",
        destination_station_id="NR05",
        travel_date="2026-10-01",
        fare_class="standard",
        seat_id=booked_seat_id
    )
    print("Result:", ok2, res2)

    print("\n=== B10: execute_cancellation ===")
    new_booking_id = res['booking_id']
    print(f"Cancelling booking {new_booking_id}...")
    cancel_ok, cancel_res = execute_cancellation(new_booking_id, "RU01")
    print("Result:", cancel_ok, cancel_res)
    
    print(f"Cancelling again {new_booking_id}...")
    cancel_ok2, cancel_res2 = execute_cancellation(new_booking_id, "RU01")
    print("Result:", cancel_ok2, cancel_res2)

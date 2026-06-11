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

print("=== B6: query_user_profile ===")
print("Known:", query_user_profile("alice.tan@email.com"))
print("Unknown:", query_user_profile("not_exist@email.com"))

print("\n=== B7: query_user_bookings ===")
bookings = query_user_bookings("alice.tan@email.com")
print("National Rail:", len(bookings.get('national_rail', [])))
if len(bookings.get('national_rail', [])) > 0:
    print("First NR booking:", bookings['national_rail'][0]['booking_id'])
    
print("Metro:", len(bookings.get('metro', [])))

print("Unknown:", query_user_bookings("not_exist@email.com"))

print("\n=== B8: query_payment_info ===")
# Use one of the bookings from B7
if len(bookings.get('national_rail', [])) > 0:
    b_id = bookings['national_rail'][0]['booking_id']
    print(f"Known {b_id}:", query_payment_info(b_id))
print("Unknown:", query_payment_info("BK-999999"))

print("\n=== B9: execute_booking ===")
# Try to book a seat for Alice
# We need a valid schedule_id, origin, destination, travel_date, seat
print("Trying to book NR_SCH01, NR01->NR05, 2026-10-01, A01...")
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

print("\nTrying to book the SAME seat again...")
ok2, res2 = execute_booking(
    user_id="RU01",
    schedule_id="NR_SCH01",
    origin_station_id="NR01",
    destination_station_id="NR05",
    travel_date="2026-10-01",
    fare_class="standard",
    seat_id="A01"
)
print("Result:", ok2, res2)

print("\n=== B10: execute_cancellation ===")
if ok:
    new_booking_id = res['booking_id']
    print(f"Cancelling booking {new_booking_id}...")
    cancel_ok, cancel_res = execute_cancellation(new_booking_id, "RU01")
    print("Result:", cancel_ok, cancel_res)
    
    print(f"Cancelling again {new_booking_id}...")
    cancel_ok2, cancel_res2 = execute_cancellation(new_booking_id, "RU01")
    print("Result:", cancel_ok2, cancel_res2)

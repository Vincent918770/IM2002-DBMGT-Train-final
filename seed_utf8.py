"""
Seed PostgreSQL with all TransitFlow mock data from train-mock-data/.

Usage:
    python skeleton/seed_postgres.py

Run AFTER docker-compose up -d.
You must first design and create your tables in databases/relational/schema.sql.
Safe to re-run: implement your inserts with ON CONFLICT DO NOTHING.
"""

import json
import os
import sys

import psycopg2
from psycopg2.extras import execute_values

# ?? argon2-cffi嚗?澆?蝣潮?皝????pip install argon2-cffi ????????????????????
from argon2 import PasswordHasher

# ?? resolve paths ????????????????????????????????????????????????????????????
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


# ?? seeders ??????????????????????????????????????????????????????????????????

def seed_metro_stations(cur):
    """撖怠 metro_stations 銵具?    敹賜 JSON 銝剔? interchange_metro_lines ??adjacent_stations嚗漱??Neo4j ??嚗?    """
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
            # lines 甈???Schema 銝剔 TEXT[]嚗?亙??Python list嚗sycopg2 ?????            item.get("lines", None),
        ))
    n = insert_many(cur, "metro_stations", columns, rows)
    print(f"  metro_stations: {n} rows inserted")


def seed_national_rail_stations(cur):
    """撖怠 national_rail_stations 銵具?    敹賜 JSON 銝剔? interchange_national_rail_lines ??adjacent_stations嚗漱??Neo4j ??嚗?    """
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
    """撖怠 metro_schedules 銝餉”嚗蒂撅?撌Ｙ????撖怠 metro_schedule_stops ?敦銵具?
    JSON 蝯?嚗?      - stops_in_order: ["MS20", "MS05", ...]          ????enumerate ?? stop_order
      - travel_time_from_origin_min: {"MS20": 0, ...}  ??隞?station_id ??key ?亥岷銵???
    """
    data = load("metro_schedules.json")

    # ?? 銝餉” ??
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

    # ?? ?敦銵剁?metro_schedule_stops ??
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
                idx + 1,  # stop_order 敺?1 ??
                travel_times.get(station_id, None),
            ))
    n = insert_many(cur, "metro_schedule_stops", stop_columns, stop_rows)
    print(f"  metro_schedule_stops: {n} rows inserted")


def seed_national_rail_schedules(cur):
    """撖怠 national_rail_schedules 銝餉”嚗蒂撅?撌Ｙ?鞈?撖怠銝撐?敦銵剁?
    1. national_rail_schedule_stops ? ??蝡?+ ??銝?
    2. national_rail_fares           ? ??蟡典

    ??蝡?(stops_in_order)     ??is_passed_through = false
    ??銝? (passed_through_stations) ??is_passed_through = true
    """
    data = load("national_rail_schedules.json")

    # ?? 銝餉” ??
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

    # ?? ?敦銵?1嚗ational_rail_schedule_stops ??
    # ????? stops_in_order (is_passed_through=false) ??passed_through_stations (is_passed_through=true)
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

        # 撱箇?銝??雿菜???暺??恍?蝡???銝虫?銵????????游?銵?        # ??蝡??Ⅱ??頠?????銝???銋?賢?曉 travel_times 銝哨?閬?JSON ??嚗?        # ?箔?蝯阡?蝡???蝡??迤蝣箇? stop_order嚗?????蔥敺?摨?        all_stations_info = []

        # ???蝡?        for station_id in stops_in_order:
            all_stations_info.append({
                "station_id": station_id,
                "travel_time": travel_times.get(station_id, None),
                "is_passed_through": False,
            })

        # ???銝???嚗???曉 travel_times 銝哨?travel_time 閮剔 None嚗?        for station_id in passed_through:
            all_stations_info.append({
                "station_id": station_id,
                "travel_time": travel_times.get(station_id, None),
                "is_passed_through": True,
            })

        # 靘?頠???摨?None ??敺?        all_stations_info.sort(key=lambda x: (x["travel_time"] is None, x["travel_time"] or 0))

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

    # ?? ?敦銵?2嚗ational_rail_fares ??
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
    """撖怠銝撐銵剁?
    1. national_rail_seat_layouts ? 摨找??蔭銝餉”
    2. national_rail_coaches      ? 頠??敦嚗oach_id ??SERIAL ?芸??Ｙ?嚗?    3. national_rail_seats         ? 摨找??敦

    ?望 national_rail_seats ??FK ?? national_rail_coaches ??SERIAL PK嚗?    ???INSERT coach 銝血????? coach_id嚗??賣迤蝣箸???seats??    ?迨 coaches ??seats ?∠???蝑??    """
    data = load("national_rail_seat_layouts.json")

    # ?? 銝餉”嚗ational_rail_seat_layouts ??
    layout_columns = ["layout_id", "schedule_id"]
    layout_rows = []
    for item in data:
        layout_rows.append((
            item.get("layout_id", None),
            item.get("schedule_id", None),
        ))
    n = insert_many(cur, "national_rail_seat_layouts", layout_columns, layout_rows)
    print(f"  national_rail_seat_layouts: {n} rows inserted")

    # ?? ?敦銵剁?national_rail_coaches + national_rail_seats ??
    coach_insert_count = 0
    seat_insert_count = 0

    for item in data:
        layout_id = item.get("layout_id", None)
        coaches = item.get("coaches", [])

        for coach_data in coaches:
            coach_name = coach_data.get("coach", None)
            fare_class = coach_data.get("fare_class", None)

            # ? coach 銝血???SERIAL ?Ｙ???coach_id
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
                # 撌脣??剁?ON CONFLICT嚗??閬閰Ｗ?敺?coach_id
                cur.execute(
                    """
                    SELECT coach_id FROM national_rail_coaches
                    WHERE layout_id = %s AND coach_name = %s
                    """,
                    (layout_id, coach_name),
                )
                result = cur.fetchone()
                if result is None:
                    continue  # ??銝????            coach_id = result[0]
            coach_insert_count += 1

            # ?閰脰?撱????漣雿?            seats = coach_data.get("seats", [])
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
    """撖怠 users 銝餉”??users_confidential 璈?銵具?
    ?? 撖Ⅳ摰閮剛?隤芣? ??????????????????????????????????????????????????????????
    ?∠ argon2id 瞍?瘜?argon2-cffi 憟辣嚗脰?撖Ⅳ?? (Password Hashing)??    ?貊?嚗?      1. Argon2 ?瑕??航矽?渡????砍?蝝?(cost factor)???閮擃???(memory cost)??         ??? (time cost) ?像銵漲 (parallelism)嚗???萇戌 GPU/ASIC ?游??渲圾??      2. 憟辣??瘥?撖Ⅳ瘛瑕銝??撅祇璈?Salt??銝血? Salt ??? Hash 蝯?
         撠??銝摮葡嚗撘?$argon2id$v=...m=...t=...p=...$salt$hash嚗?         ?迨?喃蝙?拐?雿輻?身摰??函??撖Ⅳ嚗?? Hash 摮葡銋??嗡???
         ?迨敺孵??脩戌?蔗?寡”?餅? (rainbow-table attacks)??      3. Schema 銝剜??蝡? salt 甈?嚗迨閮剛?甇?末?芷?撠銝??摮葡?湔摮
         users_confidential.password 甈??喳嚗??????銵恣??    ??????????????????????????????????????????????????????????????????????????????
    """
    data = load("registered_users.json")

    # ????Argon2 撖Ⅳ????    # PasswordHasher ?身雿輻 argon2id 霈?嚗??雿喳??函?改?
    #   - time_cost=3 (餈凋誨甈⊥)
    #   - memory_cost=65536 (64 MB 閮擃?
    #   - parallelism=4 (撟唾??瑁?蝺)
    # 隞乩????雿踹??游??渲圾??蝞誨?寞扔擃?    ph = PasswordHasher()

    # ?? 銝餉”嚗sers ??
    user_columns = [
        "user_id", "full_name", "email", "phone",
        "date_of_birth", "registered_at", "is_active",
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
        ))
    n = insert_many(cur, "users", user_columns, user_rows)
    print(f"  users: {n} rows inserted")

    # ?? 璈?銵剁?users_confidential ??
    conf_columns = ["user_id", "password", "secret_question", "secret_answer"]
    conf_rows = []
    for item in data:
        raw_password = item.get("password", None)
        raw_secret_answer = item.get("secret_answer", None)

        # 雿輻 argon2id ?脰?撖Ⅳ??嚗?        # ph.hash() ????璈?Salt 銝血??嗉? Hash 蝯?撠??銝摮葡嚗?        # 蝣箔??詨?撖Ⅳ????? Hash嚗??蝳血蔗?寡”?餅? (rainbow-table attacks)??        hashed_password = ph.hash(raw_password) if raw_password else None
        hashed_secret_answer = ph.hash(raw_secret_answer) if raw_secret_answer else None

        conf_rows.append((
            item.get("user_id", None),
            hashed_password,
            item.get("secret_question", None),
            hashed_secret_answer,
        ))
    n = insert_many(cur, "users_confidential", conf_columns, conf_rows)
    print(f"  users_confidential: {n} rows inserted")


def seed_national_rail_bookings(cur):
    """撖怠 national_rail_bookings 銵具?""
    data = load("bookings.json")
    columns = [
        "booking_id", "user_id", "schedule_id",
        "origin_station_id", "destination_station_id",
        "travel_date", "departure_time",
        "ticket_type", "fare_class", "coach", "seat_id",
        "stops_travelled", "amount_usd", "status",
        "booked_at", "travelled_at",
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
            item.get("fare_class", None),
            item.get("coach", None),
            item.get("seat_id", None),
            item.get("stops_travelled", None),
            item.get("amount_usd", None),
            item.get("status", None),
            item.get("booked_at", None),
            item.get("travelled_at", None),
        ))
    n = insert_many(cur, "national_rail_bookings", columns, rows)
    print(f"  national_rail_bookings: {n} rows inserted")


def seed_metro_travels(cur):
    """撖怠 metro_travel_history 銵具?
    ?寞???嚗ay_pass_ref ?箄???批???(self-referencing FK)??    ?粹??FK ??嚗??拇甈∪神?伐?
      1. ?神?交???day_pass_ref ??????day_pass_ref ??null ????
      2. ?神?交? day_pass_ref ????甇斗?鋡怠??抒? trip_id 撌脣??剁?
    """
    data = load("metro_travel_history.json")
    columns = [
        "trip_id", "user_id", "schedule_id",
        "origin_station_id", "destination_station_id",
        "travel_date", "ticket_type", "day_pass_ref",
        "stops_travelled", "amount_usd", "status",
        "purchased_at", "travelled_at",
    ]

    # ???拇嚗 day_pass_ref ??撖恬???day_pass_ref ??撖?    rows_no_ref = []
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
            item.get("day_pass_ref", None),
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
    """撖怠 payments 銵具?""
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
    """撖怠 feedback 銵具?""
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


# ?? main ?????????????????????????????????????????????????????????????????????

def main():
    print("Connecting to PostgreSQL...")
    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    try:
        print("Seeding tables (dependency order):")

        # ?? 蝚砌?撅歹??∪??萎?鞈渡??箇?銵???
        seed_metro_stations(cur)           # metro_stations (鋡?metro_schedules?etro_travel_history ?)
        seed_national_rail_stations(cur)   # national_rail_stations (鋡?national_rail_schedules?ookings ?)
        seed_users(cur)                    # users + users_confidential (鋡?bookings?etro_travel_history?eedback ?)

        # ?? 蝚砌?撅歹?靘陷蝚砌?撅斤??銵???
        seed_metro_schedules(cur)          # metro_schedules + metro_schedule_stops (靘陷 metro_stations)
        seed_national_rail_schedules(cur)  # national_rail_schedules + schedule_stops + fares (靘陷 national_rail_stations)

        # ?? 蝚砌?撅歹?靘陷蝚砌?撅斤?摨找??蔭 ??
        seed_seat_layouts(cur)             # seat_layouts + coaches + seats (靘陷 national_rail_schedules)

        # ?? 蝚砍?撅歹?靘陷雿輻???銵函?鈭斗?蝝????
        seed_national_rail_bookings(cur)   # national_rail_bookings (靘陷 users, national_rail_schedules, national_rail_stations)
        seed_metro_travels(cur)            # metro_travel_history (靘陷 users, metro_schedules, metro_stations嚗 self-ref FK)

        # ?? 蝚砌?撅歹?靘陷鈭斗?蝝??敺?銵???
        seed_payments(cur)                 # payments (booking_id ??FK ?嚗??摩銝?鞈?bookings/metro_travel_history)
        seed_feedback(cur)                 # feedback (靘陷 users嚗ooking_id ?∪??FK)

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

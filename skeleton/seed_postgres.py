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

# ── argon2-cffi：用於密碼雜湊，需先 pip install argon2-cffi ────────────────────
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
    """寫入 metro_stations 表。
    忽略 JSON 中的 interchange_metro_lines 與 adjacent_stations（交由 Neo4j 處理）。
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
            # lines 欄位在 Schema 中為 TEXT[]，直接傳入 Python list，psycopg2 會自動轉換
            item.get("lines", None),
        ))
    n = insert_many(cur, "metro_stations", columns, rows)
    print(f"  metro_stations: {n} rows inserted")


def seed_national_rail_stations(cur):
    """寫入 national_rail_stations 表。
    忽略 JSON 中的 interchange_national_rail_lines 與 adjacent_stations（交由 Neo4j 處理）。
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
    """寫入 metro_schedules 主表，並展開巢狀陣列寫入 metro_schedule_stops 明細表。

    JSON 結構：
      - stops_in_order: ["MS20", "MS05", ...]          → 用 enumerate 取得 stop_order
      - travel_time_from_origin_min: {"MS20": 0, ...}  → 以 station_id 為 key 查詢行車時間
    """
    data = load("metro_schedules.json")

    # ── 主表 ──
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

    # ── 明細表：metro_schedule_stops ──
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
                idx + 1,  # stop_order 從 1 開始
                travel_times.get(station_id, None),
            ))
    n = insert_many(cur, "metro_schedule_stops", stop_columns, stop_rows)
    print(f"  metro_schedule_stops: {n} rows inserted")


def seed_national_rail_schedules(cur):
    """寫入 national_rail_schedules 主表，並展開巢狀資料寫入三張明細表：
    1. national_rail_schedule_stops ─ 停靠站 + 過站不停
    2. national_rail_fares           ─ 艙等票價

    停靠站 (stops_in_order)     → is_passed_through = false
    過站不停 (passed_through_stations) → is_passed_through = true
    """
    data = load("national_rail_schedules.json")

    # ── 主表 ──
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

    # ── 明細表 1：national_rail_schedule_stops ──
    # 需同時處理 stops_in_order (is_passed_through=false) 與 passed_through_stations (is_passed_through=true)
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

        # 建立一個合併所有站點（含過站不停）並依行車時間排序的完整列表
        # 停靠站有明確的行車時間；過站不停的站也可能出現在 travel_times 中（視 JSON 而定）
        # 為了給過站不停的站分配正確的 stop_order，將所有站合併後排序
        all_stations_info = []

        # 加入停靠站
        for station_id in stops_in_order:
            all_stations_info.append({
                "station_id": station_id,
                "travel_time": travel_times.get(station_id, None),
                "is_passed_through": False,
            })

        # 加入過站不停的站（不會出現在 travel_times 中，travel_time 設為 None）
        for station_id in passed_through:
            all_stations_info.append({
                "station_id": station_id,
                "travel_time": travel_times.get(station_id, None),
                "is_passed_through": True,
            })

        # 依行車時間排序，None 排到最後
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

    # ── 明細表 2：national_rail_fares ──
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
    """寫入三張表：
    1. national_rail_seat_layouts ─ 座位配置主表
    2. national_rail_coaches      ─ 車廂明細（coach_id 由 SERIAL 自動產生）
    3. national_rail_seats         ─ 座位明細

    由於 national_rail_seats 的 FK 指向 national_rail_coaches 的 SERIAL PK，
    需先 INSERT coach 並取回生成的 coach_id，才能正確插入 seats。
    因此 coaches 與 seats 採用逐筆插入策略。
    """
    data = load("national_rail_seat_layouts.json")

    # ── 主表：national_rail_seat_layouts ──
    layout_columns = ["layout_id", "schedule_id"]
    layout_rows = []
    for item in data:
        layout_rows.append((
            item.get("layout_id", None),
            item.get("schedule_id", None),
        ))
    n = insert_many(cur, "national_rail_seat_layouts", layout_columns, layout_rows)
    print(f"  national_rail_seat_layouts: {n} rows inserted")

    # ── 明細表：national_rail_coaches + national_rail_seats ──
    coach_insert_count = 0
    seat_insert_count = 0

    for item in data:
        layout_id = item.get("layout_id", None)
        coaches = item.get("coaches", [])

        for coach_data in coaches:
            coach_name = coach_data.get("coach", None)
            fare_class = coach_data.get("fare_class", None)

            # 插入 coach 並取回 SERIAL 產生的 coach_id
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
                # 已存在（ON CONFLICT），需要查詢取得 coach_id
                cur.execute(
                    """
                    SELECT coach_id FROM national_rail_coaches
                    WHERE layout_id = %s AND coach_name = %s
                    """,
                    (layout_id, coach_name),
                )
                result = cur.fetchone()
                if result is None:
                    continue  # 理論上不應發生
            coach_id = result[0]
            coach_insert_count += 1

            # 插入該車廂下的所有座位
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
    """寫入 users 主表與 users_confidential 機密表。

    ── 密碼安全設計說明 ──────────────────────────────────────────────────────────
    採用 argon2id 演算法（argon2-cffi 套件）進行密碼雜湊 (Password Hashing)。
    選用理由：
      1. Argon2 具備可調整的「成本因素 (cost factor)」，包含記憶體成本 (memory cost)、
         時間成本 (time cost) 與平行度 (parallelism)，可有效抵禦 GPU/ASIC 暴力破解。
      2. 套件會自動為每組密碼混入一個「專屬隨機 Salt」，並將 Salt 連同 Hash 結果
         封裝成單一字串（格式：$argon2id$v=...m=...t=...p=...$salt$hash）。
         因此即使兩位使用者設定完全相同的密碼，產生的 Hash 字串也必然不同，
         藉此徹底防禦「彩虹表攻擊 (rainbow-table attacks)」。
      3. Schema 中沒有獨立的 salt 欄位，此設計正好只需將單一雜湊字串直接存入
         users_confidential.password 欄位即可，無需手動拆分或另行管理。
    ──────────────────────────────────────────────────────────────────────────────
    """
    data = load("registered_users.json")

    # 初始化 Argon2 密碼雜湊器
    # PasswordHasher 預設使用 argon2id 變體，具備最佳安全特性：
    #   - time_cost=3 (迭代次數)
    #   - memory_cost=65536 (64 MB 記憶體)
    #   - parallelism=4 (平行執行緒數)
    # 以上成本因素使得暴力破解的計算代價極高。
    ph = PasswordHasher()

    # ── 主表：users ──
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
            item.get("app_credit_balance", 0.00),
        ))
    n = insert_many(cur, "users", user_columns, user_rows)
    print(f"  users: {n} rows inserted")

    # ── 機密表：users_confidential ──
    conf_columns = ["user_id", "password", "secret_question", "secret_answer"]
    conf_rows = []
    for item in data:
        raw_password = item.get("password", None)
        raw_secret_answer = item.get("secret_answer", None)

        # 使用 argon2id 進行密碼雜湊：
        # ph.hash() 會自動生成隨機 Salt 並將其與 Hash 結果封裝成單一字串，
        # 確保相同密碼會產生不同的 Hash，有效防禦彩虹表攻擊 (rainbow-table attacks)。
        hashed_password = ph.hash(raw_password) if raw_password else None
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
    """寫入 national_rail_bookings 表。"""
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
    """寫入 metro_travel_history 表。

    特殊處理：day_pass_ref 為自我參照外鍵 (self-referencing FK)。
    為避免 FK 違規，分兩批次寫入：
      1. 先寫入沒有 day_pass_ref 的記錄（或 day_pass_ref 為 null 的記錄）
      2. 再寫入有 day_pass_ref 的記錄（此時被參照的 trip_id 已存在）
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

    # 分成兩批：無 day_pass_ref 的先寫，有 day_pass_ref 的後寫
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
    """寫入 payments 表。"""
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
    """寫入 feedback 表。"""
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

        # ── 第一層：無外鍵依賴的基礎表 ──
        seed_metro_stations(cur)           # metro_stations (被 metro_schedules、metro_travel_history 參照)
        seed_national_rail_stations(cur)   # national_rail_stations (被 national_rail_schedules、bookings 參照)
        seed_users(cur)                    # users + users_confidential (被 bookings、metro_travel_history、feedback 參照)

        # ── 第二層：依賴第一層的時刻表 ──
        seed_metro_schedules(cur)          # metro_schedules + metro_schedule_stops (依賴 metro_stations)
        seed_national_rail_schedules(cur)  # national_rail_schedules + schedule_stops + fares (依賴 national_rail_stations)

        # ── 第三層：依賴第二層的座位配置 ──
        seed_seat_layouts(cur)             # seat_layouts + coaches + seats (依賴 national_rail_schedules)

        # ── 第四層：依賴使用者與時刻表的交易紀錄 ──
        seed_national_rail_bookings(cur)   # national_rail_bookings (依賴 users, national_rail_schedules, national_rail_stations)
        seed_metro_travels(cur)            # metro_travel_history (依賴 users, metro_schedules, metro_stations；含 self-ref FK)

        # ── 第五層：依賴交易紀錄的後續表 ──
        seed_payments(cur)                 # payments (booking_id 無 FK 限制，但邏輯上依賴 bookings/metro_travel_history)
        seed_feedback(cur)                 # feedback (依賴 users；booking_id 無嚴格 FK)
        seed_lost_items(cur)               # lost_items (依賴 stations, users)
        seed_penalties(cur)                # penalties (依賴 users)

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

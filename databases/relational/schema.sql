-- ============================================================
--  TransitFlow PostgreSQL Schema
--  Seed data is loaded separately by: python skeleton/seed_postgres.py
--
--  TWO ROLES:
--    1. Relational  → dual-network transit data you design below
--    2. Vector      → policy documents for RAG (provided — do not modify)
-- ============================================================

-- ============================================================
--  STUDENT TASK — Design and create your relational tables here
--
--  Start from the mock data in train-mock-data/:
--    metro_stations.json, national_rail_stations.json
--    metro_schedules.json, national_rail_schedules.json
--    national_rail_seat_layouts.json
--    registered_users.json
--    bookings.json, metro_travel_history.json
--    payments.json, feedback.json
--
--  Think about:
--    - What tables do you need?
--    - What columns and data types?
--    - Which fields are primary keys? Which are foreign keys?
--    - What constraints make sense?
--
--  Apply your schema with:
--    docker-compose down -v && docker-compose up -d
-- ============================================================

-- secret_answer、secret_question、password
-- =========================================================================
-- [ 關於密碼與敏感資訊 (users_confidential) 的設計 ]
-- 說明：將密碼等敏感資訊獨立成 `users_confidential` 表，以符合資訊分離最佳實務。
-- 1. 資安保護：符合最小權限原則，僅限管理員存取；若發生外洩，也可限縮損害範圍。
-- 2. 關聯性：透過 `user_id` 作為 PK 與 FK，確保一對一嚴格綁定。
-- 📌 結論 (Seed 腳本注意事項)：新增使用者時，必須同時寫入兩張表，並確保 user_id 一致。
--
-- [ Users Confidential Information Design ]
-- Description: Extracted sensitive data into `users_confidential` for best practice data separation.
-- 1. Security: Follows least privilege principle (admin only); minimizes blast radius in breaches.
-- 2. Relationship: Strict 1-to-1 binding using `user_id` as PK & FK.
-- 📌 Note for Seed Script: Must insert into both tables simultaneously with matching user_id.
-- =========================================================================

-- 提問：若考慮使用者刪除帳號之情況，該如何處理？ --解：用 is_active 解決，保留交易與歷史紀錄
-- Q: How to handle user account deletion? -- A: Use is_active for soft deletion to retain transaction history.
-- 提問：users_confidential 在使用者刪除帳號時，考慮 1. 同樣 is_active 2. 刪掉
-- Q: Should users_confidential be soft-deleted or hard-deleted? 
CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(50) PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    registered_at TIMESTAMP,
    is_active BOOLEAN
);

-- 將敏感資訊獨立成表，並設置外鍵與級聯刪除 (CASCADE)，增強安全性。
-- Extracted sensitive info into a separate table with cascading delete for security.
-- !! 缺少 hash 值、加密方式
-- !! Missing password hashing/encryption
CREATE TABLE IF NOT EXISTS users_confidential (
    user_id VARCHAR(50) PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    password VARCHAR(255) NOT NULL,
    secret_question VARCHAR(255),
    secret_answer VARCHAR(255)
);

-- 缺 interchange_metro_lines、adjacent_stations
-- Missing interchange_metro_lines, adjacent_stations
-- =========================================================================
-- [ 關於「轉乘路線欄位 (interchange_lines)」的刪除與架構修正說明 ]
-- 說明：為避免違反 1NF 與資料冗餘，移除 `interchange_lines` 陣列欄位。
-- 1. 原因：資料與 `lines` 重疊；且複雜的轉乘網路交由 Neo4j 處理更合適。
-- 2. 替代方案：PostgreSQL 僅保留 `is_interchange_xxx` 布林值標籤供 UI 快速查詢；詳細轉乘路線透過 Neo4j 查詢。
-- 📌 結論 (Seed 腳本注意事項)：忽略 JSON 的路線陣列，只需寫入 true/false 布林值即可。
--
-- [ Interchange Lines Column Removal & Architecture Update ]
-- Description: Removed `interchange_lines` array columns to prevent 1NF violation and data redundancy.
-- 1. Reason: Overlaps with `lines`; complex graph queries are better handled by Neo4j.
-- 2. Alternative: PostgreSQL retains lightweight `is_interchange_xxx` booleans; Neo4j handles detailed routes.
-- 📌 Note for Seed Script: Ignore JSON line arrays. Only insert true/false boolean flags.
-- =========================================================================
-- =========================================================================
-- [ 關於「相鄰車站與行車時間資料 (adjacent_stations)」的刪除與架構修正說明 ]
-- 說明：為避免違反 1NF，PostgreSQL 不儲存 `adjacent_stations` 這種複雜的物件陣列。
-- 策略：採用多資料庫並存 (Polyglot Persistence)，PostgreSQL 專注於交易紀錄，Neo4j 負責處理網路拓樸。
-- 📌 團隊分工結論：請負責 Neo4j 的成員將 JSON 中的 adjacent_stations 轉化為 Graph Relationships。
--
-- [ Adjacent Stations Data Removal & Architecture Update ]
-- Description: Excluded `adjacent_stations` object arrays from PostgreSQL to prevent 1NF violation.
-- Strategy: Polyglot persistence. PostgreSQL handles core transactions; Neo4j handles network topology.
-- 📌 Note for Neo4j Team: Parse `adjacent_stations` from JSON directly into Graph Relationships.
-- =========================================================================
CREATE TABLE IF NOT EXISTS metro_stations (
    station_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_interchange_metro BOOLEAN,
    is_interchange_national_rail BOOLEAN,
    interchange_national_rail_station_id VARCHAR(10),
    lines TEXT[]
);

-- 缺 interchange_national_rail_lines、adjacent_stations
-- Missing interchange_national_rail_lines, adjacent_stations
-- =========================================================================
-- [ 關於「轉乘路線欄位 (interchange_lines)」的刪除與架構修正說明 ]
-- 說明：為避免違反 1NF 與資料冗餘，移除 `interchange_lines` 陣列欄位。
-- 1. 原因：資料與 `lines` 重疊；且複雜的轉乘網路交由 Neo4j 處理更合適。
-- 2. 替代方案：PostgreSQL 僅保留 `is_interchange_xxx` 布林值標籤供 UI 快速查詢；詳細轉乘路線透過 Neo4j 查詢。
-- 📌 結論 (Seed 腳本注意事項)：忽略 JSON 的路線陣列，只需寫入 true/false 布林值即可。
--
-- [ Interchange Lines Column Removal & Architecture Update ]
-- Description: Removed `interchange_lines` array columns to prevent 1NF violation and data redundancy.
-- 1. Reason: Overlaps with `lines`; complex graph queries are better handled by Neo4j.
-- 2. Alternative: PostgreSQL retains lightweight `is_interchange_xxx` booleans; Neo4j handles detailed routes.
-- 📌 Note for Seed Script: Ignore JSON line arrays. Only insert true/false boolean flags.
-- =========================================================================
-- =========================================================================
-- [ 關於「相鄰車站與行車時間資料 (adjacent_stations)」的刪除與架構修正說明 ]
-- 說明：為避免違反 1NF，PostgreSQL 不儲存 `adjacent_stations` 這種複雜的物件陣列。
-- 策略：採用多資料庫並存 (Polyglot Persistence)，PostgreSQL 專注於交易紀錄，Neo4j 負責處理網路拓樸。
-- 📌 團隊分工結論：請負責 Neo4j 的成員將 JSON 中的 adjacent_stations 轉化為 Graph Relationships。
--
-- [ Adjacent Stations Data Removal & Architecture Update ]
-- Description: Excluded `adjacent_stations` object arrays from PostgreSQL to prevent 1NF violation.
-- Strategy: Polyglot persistence. PostgreSQL handles core transactions; Neo4j handles network topology.
-- 📌 Note for Neo4j Team: Parse `adjacent_stations` from JSON directly into Graph Relationships.
-- =========================================================================
CREATE TABLE IF NOT EXISTS national_rail_stations (
    station_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_interchange_national_rail BOOLEAN,
    is_interchange_metro BOOLEAN,
    interchange_metro_station_id VARCHAR(10),
    lines TEXT[]
);

-- travel_time_from_origin_min 寫於 metro_schedule_stops -- Question
-- travel_time_from_origin_min is moved to metro_schedule_stops -- Question
-- stops_in_order 寫於 metro_schedule_stops
-- stops_in_order is moved to metro_schedule_stops
-- =========================================================================
-- [ 💡 關於「時刻表停靠站與行車時間 (stops_in_order & travel_time...)」的架構修正說明 ]
-- 說明：為符合 1NF，將陣列欄位抽出，建立 `metro_schedule_stops` 垂直明細表。
-- 1. 優勢：將慢速的陣列解析轉換為快速的精準查詢，並加上外鍵防呆機制。
-- 2. 欄位更名：`stops_in_order` 改為單數的 `stop_order` 以精確表達單一站點序號。
-- 📌 結論 (Seed 腳本注意事項)：請分兩階段寫入。先寫入主表，再跑迴圈將陣列拆解並寫入明細表。
--
-- [ 💡 Schedule Stops & Travel Time Architecture Update ]
-- Description: Extracted arrays into `metro_schedule_stops` detail table to comply with 1NF.
-- 1. Advantages: Replaces slow array parsing with fast precise queries; enables FK data integrity.
-- 2. Renaming: `stops_in_order` renamed to singular `stop_order` for per-row clarity.
-- 📌 Note for Seed Script: Two-step insertion. Insert main table first, then loop array to insert details.
-- =========================================================================
CREATE TABLE IF NOT EXISTS metro_schedules (
    schedule_id VARCHAR(20) PRIMARY KEY,
    line VARCHAR(10),
    direction VARCHAR(20),
    origin_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    destination_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    first_train_time TIME,
    last_train_time TIME,
    base_fare_usd NUMERIC(5,2),
    per_stop_rate_usd NUMERIC(5,2),
    frequency_min INT,
    operates_on TEXT[]
);

-- checked name
-- 更名來由已於上方註解說明
-- renaming reasons mentioned in the comments above
CREATE TABLE IF NOT EXISTS metro_schedule_stops (
    schedule_id VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    stop_order INT,
    travel_time_from_origin_min INT,
    PRIMARY KEY (schedule_id, station_id)
);

-- stops_in_order 寫於 national_rail_schedule_stops (stop_order 不確定是否相同)
-- stops_in_order is moved to national_rail_schedule_stops (stop_order)
-- travel_time_from_origin_min 寫於 national_rail_schedule_stops
-- travel_time_from_origin_min is moved to national_rail_schedule_stops
-- 在上方註解有提及更名來由 (stops_in_order -> stop_order)
-- renaming reasons mentioned in the comments above

-- fare_classes 寫於 national_rail_fares
-- fare_classes is moved to national_rail_fares
-- =========================================================================
-- [ 關於「多種票價艙等 (fare_classes)」的架構修正說明 ]
-- 說明：將 JSON 的 `fare_classes` 抽出建立 `national_rail_fares` 票價明細表。
-- 1. 目的：拒絕寫死欄位，提升擴充性 (未來新增艙等不需改 Schema)；同時大幅提升查詢效能。
-- 📌 結論 (Seed 腳本注意事項)：請分兩階段寫入。先寫入主表，再將艙等字典拆解寫入票價明細表。
--
-- [ Fare Classes Architecture Update ]
-- Description: Extracted `fare_classes` into a separate `national_rail_fares` detail table.
-- 1. Purpose: Avoids hardcoded columns for scalability; improves query efficiency.
-- 📌 Note for Seed Script: Two-step insertion. Insert main table first, then parse dictionary into detail table.
-- =========================================================================
CREATE TABLE IF NOT EXISTS national_rail_schedules (
    schedule_id VARCHAR(20) PRIMARY KEY,
    line VARCHAR(10),
    service_type VARCHAR(20),
    direction VARCHAR(20),
    origin_station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    destination_station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    first_train_time TIME,
    last_train_time TIME,
    frequency_min INT,
    operates_on TEXT[]
);

-- 多 is_passed_through
-- Added is_passed_through
-- =========================================================================
-- [ 關於「過站不停 (is_passed_through)」的架構設計說明 ]
-- 說明：在明細表新增 `is_passed_through` 布林值，統合有停靠與過站不停的車站。
-- 1. 目的：單一真實來源，不需開兩張表；保留過站不停的紀錄以利行車調度與系統追蹤。
-- 📌 結論 (Seed 腳本注意事項)：停靠站設為 false，過站不停設為 true。
--
-- [ Passed Through Stations Architecture Update ]
-- Description: Added `is_passed_through` flag to combine stopping and non-stopping stations.
-- 1. Purpose: Single source of truth; tracks occupied rail resources even if not stopping.
-- 📌 Note for Seed Script: Insert stopping stations as false, passed stations as true.
-- =========================================================================
CREATE TABLE IF NOT EXISTS national_rail_schedule_stops (
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    stop_order INT,
    travel_time_from_origin_min INT,
    is_passed_through BOOLEAN,
    PRIMARY KEY (schedule_id, station_id)
);

-- base_fare_usd、per_stop_rate_usd 為原多值屬性拆解
-- base_fare_usd, per_stop_rate_usd extracted from multi-valued attribute
-- =========================================================================
-- [ 關於「票價費率 (base_fare_usd & per_stop_rate_usd)」的正規化拆分解釋 ]
-- 說明：將複合的多值屬性拆解成兩個獨立的數值欄位，以符合 1NF。
-- 1. 目的：確保資料原子性；允許 SQL 直接進行票價數學運算，效率極高。
-- 📌 結論 (Seed 腳本注意事項)：將 JSON 中的數字提取為這兩個獨立欄位即可。
--
-- [ Fare Rates Normalization Update ]
-- Description: Extracted base fare and per-stop rates into independent numeric columns for 1NF.
-- 1. Purpose: Ensures atomicity; allows direct mathematical operations within SQL.
-- 📌 Note for Seed Script: Parse the corresponding JSON numbers into these two columns.
-- =========================================================================
CREATE TABLE IF NOT EXISTS national_rail_fares (
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    fare_class VARCHAR(20),
    base_fare_usd NUMERIC(5,2),
    per_stop_rate_usd NUMERIC(5,2),
    PRIMARY KEY (schedule_id, fare_class)
);

CREATE TABLE IF NOT EXISTS national_rail_seat_layouts (
    layout_id VARCHAR(20) PRIMARY KEY,
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id)
);

-- 提問：national_rail_coaches 為何不須聯合 schedule_id？ --解：因為 layout_id 已經對應到 schedule_id，不同車次不一定共用。
-- Q: Why doesn't national_rail_coaches need schedule_id? -- A: Because layout_id implies it.
-- 提問：於 .sql 和 .json 中使用不同變數名稱會影響引入嗎 (coach_id vs coach) --解：不會，腳本對應即可。
-- Q: Does using different variable names in .sql/.json affect import? -- A: No, maps via script.
-- 註解：coach: 車廂編號、fare_class: 票價等級、layout_id: 座位配置的唯一識別碼
-- Note: coach = coach code, fare_class = fare tier, layout_id = unique seat layout ID

CREATE TABLE IF NOT EXISTS national_rail_coaches (
    coach_id SERIAL PRIMARY KEY,
    layout_id VARCHAR(20) REFERENCES national_rail_seat_layouts(layout_id),
    coach_name VARCHAR(20),
    fare_class VARCHAR(20)
);

-- 註解：seat_id 座位號碼、row: 排數、column: 行或位置
-- Note: seat_id = seat number, row = row number, column = column position (e.g., window/aisle)

CREATE TABLE IF NOT EXISTS national_rail_seats (
    seat_id VARCHAR(10),
    coach_id INT REFERENCES national_rail_coaches(coach_id),
    row_num INT,
    column_letter VARCHAR(2),
    PRIMARY KEY (seat_id, coach_id)
);

-- checked name
CREATE TABLE IF NOT EXISTS national_rail_bookings (
    booking_id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    origin_station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    destination_station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    travel_date DATE,
    departure_time TIME,
    ticket_type VARCHAR(20),
    fare_class VARCHAR(20),
    coach VARCHAR(5),
    seat_id VARCHAR(10),
    stops_travelled INT,
    amount_usd NUMERIC(8,2),
    status VARCHAR(20),
    booked_at TIMESTAMP,
    travelled_at TIMESTAMP
);

-- 提問：新增 day_pass_ref，不確定是否需要，無相關欄位存在於 .json？ --解：檔案中其實已存在。
-- Q: Added day_pass_ref, not sure if needed? -- A: It does exist in the JSON.
-- 提問：若不同日但搭乘同班次，是否會被當作同一天的 day_pass？ --解：不會，因為有 travel_date 區分。
-- Q: Will rides on different days be treated as same day_pass? -- A: No, distinguished by travel_date.
CREATE TABLE IF NOT EXISTS metro_travel_history (
    trip_id VARCHAR(20) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    schedule_id VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    origin_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    destination_station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    travel_date DATE,
    ticket_type VARCHAR(20),
    day_pass_ref VARCHAR(20) REFERENCES metro_travel_history(trip_id),
    stops_travelled INT,
    amount_usd NUMERIC(8,2),
    status VARCHAR(20),
    purchased_at TIMESTAMP,
    travelled_at TIMESTAMP
);

-- checked name
CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(20) PRIMARY KEY,
    booking_id VARCHAR(20),
    amount_usd NUMERIC(8,2),
    method VARCHAR(20),
    status VARCHAR(20),
    paid_at TIMESTAMP
);
-- checked name
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id VARCHAR(20) PRIMARY KEY,
    booking_id VARCHAR(20),
    user_id VARCHAR(50) REFERENCES users(user_id),
    rating INT,
    comment TEXT,
    submitted_at TIMESTAMP
);


-- ============================================================
--  VECTOR SCHEMA  (RAG / Help Desk) — do not modify
-- ============================================================

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_documents (
    id          SERIAL       PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    category    VARCHAR(50)  NOT NULL,  -- 'refund', 'booking', 'conduct'
    content     TEXT         NOT NULL,
    -- 768-dim  → Ollama nomic-embed-text (default)
    -- 3072-dim → Gemini gemini-embedding-001
    -- If you switch LLM_PROVIDER to gemini, change to vector(3072) and reset the database.
    embedding   vector(768),
    source_file VARCHAR(200),
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- Index for fast cosine similarity search
CREATE INDEX IF NOT EXISTS ON policy_documents USING hnsw (embedding vector_cosine_ops);

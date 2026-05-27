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

CREATE TABLE IF NOT EXISTS users (
    user_id VARCHAR(50) PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    registered_at TIMESTAMP,
    is_active BOOLEAN
);
--把password等敏感資訊獨立成一個表，並設置user_id為外鍵參照users表，並在users表刪除時級聯刪除users_confidential表中的相關記錄，以增強數據安全性和隱私保護。
CREATE TABLE IF NOT EXISTS users_confidential (
    user_id VARCHAR(50) PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    password VARCHAR(255) NOT NULL,
    secret_question VARCHAR(255),
    secret_answer VARCHAR(255)
);
--缺interchange_metro_lines、adjacent_stations
-- =========================================================================
-- [ 關於「轉乘路線欄位 (interchange_lines)」的刪除與架構修正說明 ]
--
-- 說明：
-- 本表原本預計配合原始 JSON 開設 `interchange_national_rail_lines` 或 `interchange_metro_lines`
-- 等文字陣列欄位 (TEXT[]) 來儲存該站可轉乘的路線詳細清單。
-- 但經團隊架構評估後，我已將此類欄位「完全移除」，原因與補救機制如下：
--
-- 1. 為什麼刪除？ (避免資料冗餘與 SQL 第一正規化衝突)
--    - 資料重疊：在原始 JSON 中，如果古亭站是轉乘站，它的 `lines` 欄位是 ["M1", "M2"]，
--      `interchange_metro_lines` 也是 ["M1", "M2"]，這在關聯式資料庫中造成嚴重的資料重複儲存。
--    - 職責分離：更重要的是，我們專案已經引入了專門處理路網圖、轉乘點拓樸的 Neo4j！
--      「哪一站可以轉乘哪幾條線」這種複雜的圖形關係，正是 Neo4j 的核心強項。
--
-- 2. 我們如何彌補這項功能？ (PostgreSQL 輕量化標籤 + Neo4j 圖形查詢)
--    - 【PostgreSQL 端 (我這邊)】：我保留了 `is_interchange_metro` 與 `is_interchange_national_rail` 
--      這兩個超輕量的布林值 (BOOLEAN) 標籤。
--      Python 後端如果只需要知道「這一站『是不是』轉乘站」（例如前端 UI 要畫轉乘 icon），
--      直接查這兩個布林值即可，速度極快，不用去解析複雜的陣列。
--    - 【Neo4j 端 (負責圖資料庫的人)】：當使用者需要查詢「具體能轉乘哪些線、如何轉乘最快」時，
--      後端程式會直接向 Neo4j 發送 Cypher 查詢。Neo4j 會透過節點與關係，
--      動態且完美地計算出所有轉乘路線。
--
-- 📌 結論 (Carol 寫 Seed 腳本請注意)：
--    下週編寫 `seed_postgres.py` 時，遇到 JSON 裡的 `interchange_xxx_lines` 欄位請直接忽略，
--    只需要把 `is_interchange_xxx` 的 true/false 塞進來即可！
--    完整的轉乘路線資料，將由負責 Neo4j 的夥伴透過 `seed.cypher` 完整倒進圖資料庫中。
-- =========================================================================
-- =========================================================================
-- [ 關於「相鄰車站與行車時間資料 (adjacent_stations)」的刪除與架構修正說明 ]
-- 關於原始 JSON 中的 "adjacent_stations" (相鄰車站與行車時間資料)：
-- 1. 關聯式資料庫限制：若在 PostgreSQL 硬存這種複雜的「物件陣列」結構，會嚴重違反 1NF 
--    (第一正規化)，導致後續 SQL 查詢必須使用極具災難性的字串解析，拉低系統效能。
--
-- 2. 多資料庫並存策略 (Polyglot Persistence)：
--    依據專案 README 規範，我們系統引入了天生擅長處理網路拓樸與地圖路網的 Neo4j。
--    因此，「車站連線、轉乘、最短行車時間」等圖形邏輯，在 PostgreSQL 中「刻意省略不存」。
--
-- 📌 團隊分工結論：
--    - PostgreSQL (我這邊)：專注管好使用者、金流、訂單、時刻表等需要嚴謹記帳的資料。
--    - Neo4j (負責 Neo4j 的人)：請在匯入資料 (Seed) 與編寫 Cypher 語法時，
--      直接將 JSON 中的 adjacent_stations 解析並建立為 Graph 中的 Relationships (連線與權重)。
-- =========================================================================
CREATE TABLE IF NOT EXISTS metro_stations (
    station_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_interchange_metro BOOLEAN,
    is_interchange_national_rail BOOLEAN,
    interchange_national_rail_station_id VARCHAR(10),
    lines TEXT[]
);
--缺interchange_national_rail_lines、adjacent_stations
-- =========================================================================
-- [ 關於「轉乘路線欄位 (interchange_lines)」的刪除與架構修正說明 ]
--
-- 說明：
-- 本表原本預計配合原始 JSON 開設 `interchange_national_rail_lines` 或 `interchange_metro_lines`
-- 等文字陣列欄位 (TEXT[]) 來儲存該站可轉乘的路線詳細清單。
-- 但經團隊架構評估後，我已將此類欄位「完全移除」，原因與補救機制如下：
--
-- 1. 為什麼刪除？ (避免資料冗餘與 SQL 第一正規化衝突)
--    - 資料重疊：在原始 JSON 中，如果古亭站是轉乘站，它的 `lines` 欄位是 ["M1", "M2"]，
--      `interchange_metro_lines` 也是 ["M1", "M2"]，這在關聯式資料庫中造成嚴重的資料重複儲存。
--    - 職責分離：更重要的是，我們專案已經引入了專門處理路網圖、轉乘點拓樸的 Neo4j！
--      「哪一站可以轉乘哪幾條線」這種複雜的圖形關係，正是 Neo4j 的核心強項。
--
-- 2. 我們如何彌補這項功能？ (PostgreSQL 輕量化標籤 + Neo4j 圖形查詢)
--    - 【PostgreSQL 端 (我這邊)】：我保留了 `is_interchange_metro` 與 `is_interchange_national_rail` 
--      這兩個超輕量的布林值 (BOOLEAN) 標籤。
--      Python 後端如果只需要知道「這一站『是不是』轉乘站」（例如前端 UI 要畫轉乘 icon），
--      直接查這兩個布林值即可，速度極快，不用去解析複雜的陣列。
--    - 【Neo4j 端 (負責圖資料庫的人)】：當使用者需要查詢「具體能轉乘哪些線、如何轉乘最快」時，
--      後端程式會直接向 Neo4j 發送 Cypher 查詢。Neo4j 會透過節點與關係，
--      動態且完美地計算出所有轉乘路線。
--
-- 📌 結論 (Carol 寫 Seed 腳本請注意)：
--    下週編寫 `seed_postgres.py` 時，遇到 JSON 裡的 `interchange_xxx_lines` 欄位請直接忽略，
--    只需要把 `is_interchange_xxx` 的 true/false 塞進來即可！
--    完整的轉乘路線資料，將由負責 Neo4j 的夥伴透過 `seed.cypher` 完整倒進圖資料庫中。
-- =========================================================================
-- =========================================================================
-- [ 關於「相鄰車站與行車時間資料 (adjacent_stations)」的刪除與架構修正說明 ]
-- 關於原始 JSON 中的 "adjacent_stations" (相鄰車站與行車時間資料)：
-- 1. 關聯式資料庫限制：若在 PostgreSQL 硬存這種複雜的「物件陣列」結構，會嚴重違反 1NF 
--    (第一正規化)，導致後續 SQL 查詢必須使用極具災難性的字串解析，拉低系統效能。
--
-- 2. 多資料庫並存策略 (Polyglot Persistence)：
--    依據專案 README 規範，我們系統引入了天生擅長處理網路拓樸與地圖路網的 Neo4j。
--    因此，「車站連線、轉乘、最短行車時間」等圖形邏輯，在 PostgreSQL 中「刻意省略不存」。
--
-- 📌 團隊分工結論：
--    - PostgreSQL (我這邊)：專注管好使用者、金流、訂單、時刻表等需要嚴謹記帳的資料。
--    - Neo4j (負責 Neo4j 的人)：請在匯入資料 (Seed) 與編寫 Cypher 語法時，
--      直接將 JSON 中的 adjacent_stations 解析並建立為 Graph 中的 Relationships (連線與權重)。
-- =========================================================================
CREATE TABLE IF NOT EXISTS national_rail_stations (
    station_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_interchange_national_rail BOOLEAN,
    is_interchange_metro BOOLEAN,
    interchange_metro_station_id VARCHAR(10),
    lines TEXT[]
);
--travel_time_from_origin_min寫於metro_schedule_stops--Question
--stops_in_order寫於metro_schedule_stops
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
--checked name
CREATE TABLE IF NOT EXISTS metro_schedule_stops (
    schedule_id VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    stop_order INT,
    travel_time_from_origin_min INT,
    PRIMARY KEY (schedule_id, station_id)
);
--stops_in_order寫於national_rail_schedule_stops(stop_order  不確定是否同)
--travel_time_from_origin_min寫於national_rail_schedule_stops
--fare_classes寫於national_rail_fares
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

-- 多is_passed_through

CREATE TABLE IF NOT EXISTS national_rail_schedule_stops (
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    stop_order INT,
    travel_time_from_origin_min INT,
    is_passed_through BOOLEAN,
    PRIMARY KEY (schedule_id, station_id)
);

-- base_fare_usd、per_stop_rate_usd為原多值屬性拆
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

CREATE TABLE IF NOT EXISTS national_rail_coaches (
    coach_id SERIAL PRIMARY KEY,
    layout_id VARCHAR(20) REFERENCES national_rail_seat_layouts(layout_id),
    coach_name VARCHAR(5),
    fare_class VARCHAR(20)
);

CREATE TABLE IF NOT EXISTS national_rail_seats (
    seat_id VARCHAR(10),
    coach_id INT REFERENCES national_rail_coaches(coach_id),
    row_num INT,
    column_letter VARCHAR(2),
    PRIMARY KEY (seat_id, coach_id)
);

--checked name
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

--checked name
CREATE TABLE IF NOT EXISTS payments (
    payment_id VARCHAR(20) PRIMARY KEY,
    booking_id VARCHAR(20),
    amount_usd NUMERIC(8,2),
    method VARCHAR(20),
    status VARCHAR(20),
    paid_at TIMESTAMP
);

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

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

--secret_answer、secret_question、password
-- =========================================================================
-- [ 關於密碼與敏感資訊 (users_confidential)的設計]
--
-- 說明：
-- 為了達成老師要求的資訊分離(user_id&password分離)的 best practice，我們將密碼、
-- 安全問題與答案獨立拆分為專門的 `users_confidential` 關聯表。
--
-- 1. 為什麼要拆？ (資安與隱私保護)
--    - 最小權限原則 (Principle of Least Privilege)：在實際的系統管理中，
--      我們只允許系統管理員 (Admin) 存取包含密碼的詳細資料。而一般員工 (Staff) 或
--      一般使用者 (User) 則被設計為只能看到 `users` 表（姓名、Email、註冊狀態），
--      無法接觸到 `users_confidential` 表。
--    - 資安事件最小化 (Minimizing Blast Radius)：一旦發生資安事件 (如資料外洩)，
--      能竊取的敏感資料範圍會被限制。
--
-- 2. 欄位與關係：
--    - 透過 `user_id` 作為 Primary Key (主鍵) 與 Foreign Key (外鍵) 的組合，
--      達成一對一的嚴格綁定。
--
-- 結論 (賴韋衡 寫 Seed 腳本請注意)：
--    在編寫 `seed_postgres.py` 建立資料時，請注意：
--    - 當要新增使用者時，必須同時在 `users` 表與 `users_confidential` 表中插入資料。
--    - `users_confidential.user_id` 欄位必須精確對應 `users.user_id`，否則資料會因為
--      外鍵約束 (Foreign Key Constraint) 而無法寫入喔！
-- =========================================================================

--提問：若考慮使用者刪除帳號之情況，該如何處理？ --解：用is_active解決，保留交易與歷史紀錄
--提問：users_confidential在使用者刪除帳號時，考慮1.同樣is_active 2.刪掉
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
--!!缺少hash值、加密方式
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
-- 📌 結論 (賴韋衡 寫 Seed 腳本請注意)：
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
-- 📌 結論 (賴韋衡 寫 Seed 腳本請注意)：
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
-- =========================================================================
-- [ 💡 關於「時刻表停靠站與行車時間 (stops_in_order & travel_time...)」的架構修正說明 ]
--
-- 說明：
-- 原始 JSON 中的 `metro_schedules.json` 將所有的停靠站與行車時間包裝成橫向的陣列與物件結構。
-- 但在關聯式資料庫中，為了符合第一正規化（1NF），我將這兩個屬性抽離，獨立設計了這張
-- `metro_schedule_stops` (明細表)，將資料轉為縱向儲存。
--
-- 1. 為什麼要拆分成明細表？ (正規化與查詢效能)
--    - 提升查詢效能 (避免大海撈針)：如果把所有站名擠在同一個陣列欄位裡，當後端要查詢
--      「哪些車次有停靠某個車站」時，資料庫必須去逐行解析陣列，效能極差。拆分成明細表後，
--      會變成極速的精準條件查詢 (WHERE station_id = '...')。
--    - 確保資料正確性 (防呆機制)：拆成明細表後，我們能在 `station_id` 加上外鍵約束 (Foreign Key)。
--      資料庫會在底層自動把關，保證塞進時刻表的每一站，都必須是車站總表裡真實存在的車站。
--
-- 2. 這兩個屬性是如何轉換的？與為什麼改名？
--    - 原始 JSON 的 `stops_in_order` (複數名詞，代表一長串停靠站名單的陣列)
--      👉 轉換成子表後，改名為單數的 `stop_order`。
--      為什麼改名？因為在子表裡，每一行資料都只代表「單一個」停靠站。如果沿用複數的
--      stops_in_order 會讓人誤以為裡面裝了一大串車站。改用單數的 stop_order 來表示
--      「這是第幾站 (整數 1, 2, 3...)」，在 SQL 語意上才是最精準、不會讓人誤會的命名。
--    - 原始 JSON 的 `travel_time_from_origin_min`
--      👉 變成了子表的一般數值欄位，獨立記錄該單一站點到起點的行車時間。
--
-- 📌 結論 (賴韋衡 寫 Seed 腳本請注意)：
--    編寫 `seed_postgres.py` 處理時刻表 JSON 時，需要進行「兩階段」資料表寫入：
--    1. 主表寫入：先把車次、線路、方向、起終點、票價等基本資訊寫入 `metro_schedules` 表。
--    2. 子表拆解：接著寫一個內部迴圈 (for loop)，將 JSON 裡的 `stops_in_order` 陣列拆解，
--       將每一個車站與對應的時間同步配對，一站一行 (垂直列印) 寫入 `metro_schedule_stops` 表中喔！
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

--checked name
--在上方註解提及更名來由
CREATE TABLE IF NOT EXISTS metro_schedule_stops (
    schedule_id VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    stop_order INT,
    travel_time_from_origin_min INT,
    PRIMARY KEY (schedule_id, station_id)
);

--stops_in_order寫於national_rail_schedule_stops(stop_order不確定是否相同)
--travel_time_from_origin_min寫於national_rail_schedule_stops
--在上方註解有提及來由
--stop_order就是由原先stops_in_order更名而來，來由已於上方提及

--fare_classes寫於national_rail_fares
-- =========================================================================
-- [ 關於「多種票價艙等 (fare_classes)」的架構修正說明 ]
--
-- 說明：
-- 原始 JSON 的 `national_rail_schedules.json` 把不同艙等（如 standard, first）
-- 的票價規則，全部包裝在一個名為 `fare_classes` 的物件中。
-- 但在 PostgreSQL 中，我將它抽離出來，獨立設計成了 `national_rail_fares` (票價明細表)。
--
-- 1. 為什麼要抽離成獨立的價目表？ (擴充性與算錢效率)
--    - 拒絕寫死欄位 (高擴充性)：如果我們在總表裡寫死 `standard_fare`、`first_fare` 
--      等欄位，未來一旦要新增「商務艙」或「敬老票」，就必須修改整個資料表結構 (ALTER TABLE)。
--      但獨立成價目表後，未來要新增任何票種，完全不用動搖資料庫架構，只要單純新增
--      一行資料 (INSERT) 就好，擴充性無敵！
--    - 算錢超快超精準：把票價獨立成表後，當使用者結帳時，後端程式只需要極為簡單的查詢：
--      `WHERE schedule_id = '...' AND fare_class = 'standard'`
--      一瞬間就能精準抓出該艙等的基本費跟每站費率，完全不需要耗費資源去解析 JSON 字串。
--
-- 📌 結論 (賴韋衡 寫 Seed 腳本請注意)：
--    編寫 `seed_postgres.py` 時，處理台鐵時刻表的 JSON 同樣需要進行「兩次」寫入：
--    1. 主表：先把車次、起終點等基本資訊寫入 `national_rail_schedules` 表。
--    2. 子表：接著寫一個內部迴圈，將 `fare_classes` 裡面的每一個艙等 (standard, first)
--       與它們對應的價錢，一筆一筆 (一種艙等一行) 獨立寫入 `national_rail_fares` 表中喔！
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

-- 多is_passed_through
-- =========================================================================
-- [ 關於「過站不停 (is_passed_through)」的架構設計說明 ]
--
-- 說明：
-- 在原始 `national_rail_schedules.json` 中，對於直達車 (Express Service)，
-- 同時記錄了有停靠的 `stops_in_order` 以及過站不停的 `passed_through_stations` 兩個陣列。
-- 為了將這兩種狀態完美融合進關聯式資料庫，我在 `national_rail_schedule_stops` 
-- 明細表中加入了 `is_passed_through` 這個布林值 (BOOLEAN) 標籤。
--
-- 1. 為什麼要這樣設計？ (化繁為簡與系統實務)
--    - 統一明細表 (單一真實來源)：我們不需要為「有停的站」和「沒停的站」開兩張不同的表。
--      只要靠這個布林值，就能在一張表內完整重現一班列車完整的行駛軌跡。
--    - 系統實務考量 (軌道佔用與安全)：即使火車「過站不停」，它依然佔用了該車站的軌道資源。
--      未來若要擴充「行車調度防撞系統」或「車站列車通過廣播 (請勿靠近月台)」，後端只需
--      查詢這張表，就能精準掌握列車駛過了哪些車站，不會因為沒停靠而失去追蹤。
--
-- 📌 結論 (賴韋衡 寫 Seed 腳本請注意)：
--    編寫 `seed_postgres.py` 時，處理台鐵直達車的 JSON 請依以下邏輯寫入明細表：
--    1. 處理 `stops_in_order` 陣列裡的車站時 👉 寫入資料，並將 `is_passed_through` 設為 `false`。
--    2. 處理 `passed_through_stations` 陣列的車站時 👉 寫入資料，並將 `is_passed_through` 設為 `true`。
--    （註：對於一般區間車 Normal Service，因為沒有過站不停的車站，只要單純處理第一點即可）
-- =========================================================================
CREATE TABLE IF NOT EXISTS national_rail_schedule_stops (
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    stop_order INT,
    travel_time_from_origin_min INT,
    is_passed_through BOOLEAN,
    PRIMARY KEY (schedule_id, station_id)
);

-- base_fare_usd、per_stop_rate_usd為原多值屬性拆
-- =========================================================================
-- [ 關於「票價費率 (base_fare_usd & per_stop_rate_usd)」的正規化拆分解釋 ]
--
-- 說明：
-- 在原始的 JSON 結構中，`fare_classes` 是一個包含了多種艙等與對應費率的
-- 「多值且複合的屬性 (Multi-valued & Composite Attribute)」。
-- 為了讓資料庫符合「第一正規化 (1NF)」，我將裡面的基本費與每站費率拆解出來，
-- 移到了全新的 `national_rail_fares` 票價明細表中。
--
-- 1. 為什麼要拆解多值屬性？ (符合 1NF 與確保資料原子性)
--    - 確保原子性 (Atomicity)：關聯式資料庫的每一個格子只能裝「一個單一的純數值」。
--      如果我們把整包 JSON 物件硬塞在總表裡，就會違反 1NF。透過建立明細表，
--      我們將原本水平發展的 JSON 物件，轉換成了「垂直發展的資料列 (Rows)」。
--    - 靈活的查詢與運算：拆解成 `base_fare_usd` (基本費) 與 `per_stop_rate_usd` (每站費率) 
--      這兩個獨立的數值 (NUMERIC) 欄位後，後端程式可以直接利用 SQL 進行數學運算
--      (例如：`base_fare_usd + (stops * per_stop_rate_usd)`)，效率極高且不會出錯。
--
-- 2. 欄位的對應關係：
--    - 原始 JSON 中 "standard" 或 "first" 的鍵名 (Key) 👉 變成 `fare_class` 欄位。
--    - 原始 JSON 中對應的兩個數字 👉 原封不動成為 `base_fare_usd` 與 `per_stop_rate_usd`。
--
-- 📌 結論 (賴韋衡 寫 Seed 腳本請注意)：
--    這張表的主鍵 (Primary Key) 是 `(schedule_id, fare_class)` 兩個欄位的組合。
--    寫入資料時，請解析 JSON 的字典結構 (Dictionary)，針對每一個艙等，
--    將車次 ID、艙等名稱、基本費、每站費率這四個值，組成一筆資料寫進這張表裡！
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
--提問：national_rail_coaches為何不須聯合schedule_id，會不會有問題      --解：應該是不同車次不一定共用
--提問：於.sql和.json中使用不同變數名稱會影響引入嗎(coach_id vs coach)

--註解：coach: 車廂的編號或代號、fare_class: 該車廂的票價等級、ayout_id: 座位配置的唯一識別碼

CREATE TABLE IF NOT EXISTS national_rail_coaches (
    coach_id SERIAL PRIMARY KEY,
    layout_id VARCHAR(20) REFERENCES national_rail_seat_layouts(layout_id),
    coach_name VARCHAR(20),
    fare_class VARCHAR(20)
);

--註解：seat_id座位號碼、row: 座位所在的「排」數、column: 座位所在的「行」或「位置」

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

--提問：新增day_pass_ref，不確定是否需要，無相關欄位存在於.json檔案中  --解：已存在
--提問：若不同日但搭乘同班次，是否會被當作同一天的day_pass  --解：不會，有travel_date
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
--checked name
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

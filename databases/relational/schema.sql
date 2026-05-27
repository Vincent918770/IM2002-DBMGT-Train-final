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
    password VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    secret_question VARCHAR(255),
    secret_answer VARCHAR(255),
    registered_at TIMESTAMP,
    is_active BOOLEAN
);

CREATE TABLE IF NOT EXISTS metro_stations (
    station_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_interchange_metro BOOLEAN,
    is_interchange_national_rail BOOLEAN,
    interchange_national_rail_station_id VARCHAR(10),
    lines TEXT[]
);

CREATE TABLE IF NOT EXISTS national_rail_stations (
    station_id VARCHAR(10) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    is_interchange_national_rail BOOLEAN,
    is_interchange_metro BOOLEAN,
    interchange_metro_station_id VARCHAR(10),
    lines TEXT[]
);

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

CREATE TABLE IF NOT EXISTS metro_schedule_stops (
    schedule_id VARCHAR(20) REFERENCES metro_schedules(schedule_id),
    station_id VARCHAR(10) REFERENCES metro_stations(station_id),
    stop_order INT,
    travel_time_from_origin_min INT,
    PRIMARY KEY (schedule_id, station_id)
);

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

CREATE TABLE IF NOT EXISTS national_rail_schedule_stops (
    schedule_id VARCHAR(20) REFERENCES national_rail_schedules(schedule_id),
    station_id VARCHAR(10) REFERENCES national_rail_stations(station_id),
    stop_order INT,
    travel_time_from_origin_min INT,
    is_passed_through BOOLEAN,
    PRIMARY KEY (schedule_id, station_id)
);

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

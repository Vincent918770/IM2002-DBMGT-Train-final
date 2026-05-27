-- ============================================================
--  TransitFlow PostgreSQL Schema
--  Seed data is loaded separately by: python skeleton/seed_postgres.py
--
--  TWO ROLES:
--    1. Relational  → dual-network transit data you design below
--    2. Vector      → policy documents for RAG (provided — do not modify)
-- ============================================================

-- 1. Users & Auth Module
CREATE TABLE users (
    user_id VARCHAR(50) PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE users_confidential (
    user_id VARCHAR(50) PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    password_hash VARCHAR(255) NOT NULL,
    secret_question VARCHAR(200),
    secret_answer_hash VARCHAR(255)
);

-- 2. Infrastructure & Schedule Module
CREATE TABLE stations (
    station_id VARCHAR(20) PRIMARY KEY,
    station_name VARCHAR(100) NOT NULL,
    network_type VARCHAR(20) NOT NULL -- 'metro' 或 'national_rail'
);

CREATE TABLE schedules (
    schedule_id VARCHAR(20) PRIMARY KEY,
    network_type VARCHAR(20) NOT NULL,
    line VARCHAR(10),
    service_type VARCHAR(20),
    direction VARCHAR(20),
    origin_station_id VARCHAR(20) REFERENCES stations(station_id),
    destination_station_id VARCHAR(20) REFERENCES stations(station_id),
    first_train_time VARCHAR(10),
    last_train_time VARCHAR(10),
    frequency_min INTEGER,
    delay_minutes INTEGER DEFAULT 0,
    status VARCHAR(20)
);

-- 3. Transactions Module
CREATE TABLE bookings (
    booking_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    schedule_id VARCHAR(20) REFERENCES schedules(schedule_id),
    travel_date DATE NOT NULL,
    amount_usd DECIMAL(10, 2) NOT NULL,
    discount_type VARCHAR(20),
    status VARCHAR(20),
    origin_station_id VARCHAR(20) REFERENCES stations(station_id),
    destination_station_id VARCHAR(20) REFERENCES stations(station_id),
    departure_time TIMESTAMP,
    ticket_type VARCHAR(20),
    fare_class VARCHAR(20),
    coach VARCHAR(10),
    seat_id VARCHAR(10),
    stops_travelled INTEGER,
    booked_at TIMESTAMP,
    travelled_at TIMESTAMP
);

CREATE TABLE trips (
    trip_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    tap_in_station_id VARCHAR(20) REFERENCES stations(station_id),
    tap_in_time TIMESTAMP NOT NULL,
    tap_out_station_id VARCHAR(20) REFERENCES stations(station_id),
    tap_out_time TIMESTAMP,
    stops_travelled INTEGER,
    fare_usd DECIMAL(10, 2),
    discount_type VARCHAR(20)
);

-- 4. Support Module
CREATE TABLE payments (
    payment_id VARCHAR(50) PRIMARY KEY,
    reference_id VARCHAR(50) NOT NULL, -- 多型外鍵 ID
    reference_type VARCHAR(20) NOT NULL CHECK (reference_type IN ('bookings', 'trips')),
    amount_usd DECIMAL(10, 2) NOT NULL,
    payment_method VARCHAR(50) NOT NULL,
    status VARCHAR(20) DEFAULT 'paid',
    paid_at TIMESTAMP NOT NULL
);

CREATE TABLE feedback (
    feedback_id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(user_id),
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    comment TEXT,
    submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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

-- Additive Build 42 sandbox and incentive schema. No existing rows are changed.
CREATE TABLE sandbox_customers (passenger_id TEXT PRIMARY KEY, provider_customer_id TEXT NOT NULL UNIQUE);
CREATE TABLE sandbox_setups (session_id TEXT PRIMARY KEY, passenger_id TEXT NOT NULL, created_ms BIGINT NOT NULL);
CREATE TABLE sandbox_cards (payment_method_id TEXT PRIMARY KEY, passenger_id TEXT NOT NULL, provider_customer_id TEXT NOT NULL);
CREATE TABLE sandbox_payments (ride_id TEXT PRIMARY KEY, passenger_id TEXT NOT NULL, amount_cents BIGINT NOT NULL CHECK(amount_cents > 0), provider_intent_id TEXT UNIQUE, status TEXT NOT NULL, updated_ms BIGINT NOT NULL);
CREATE TABLE sandbox_refunds (ride_id TEXT NOT NULL, request_key TEXT NOT NULL, amount_cents BIGINT NOT NULL CHECK(amount_cents > 0), provider_refund_id TEXT UNIQUE, status TEXT NOT NULL, created_ms BIGINT NOT NULL, PRIMARY KEY (ride_id, request_key));
CREATE TABLE finance_entries (entry_key TEXT PRIMARY KEY, ride_id TEXT NOT NULL, driver_id TEXT, kind TEXT NOT NULL, amount_cents BIGINT NOT NULL, at_ms BIGINT NOT NULL);
CREATE INDEX finance_entries_ride ON finance_entries (ride_id, at_ms);
CREATE TABLE boost_zones (id TEXT PRIMARY KEY, label TEXT NOT NULL, latitude DOUBLE PRECISION NOT NULL, longitude DOUBLE PRECISION NOT NULL, radius_km DOUBLE PRECISION NOT NULL, category TEXT NOT NULL, start_ms BIGINT NOT NULL, end_ms BIGINT NOT NULL, bonus_cents BIGINT NOT NULL, budget_cents BIGINT NOT NULL, awarded_cents BIGINT NOT NULL DEFAULT 0, enabled BIGINT NOT NULL DEFAULT 0);
CREATE TABLE boost_awards (ride_id TEXT PRIMARY KEY, zone_id TEXT NOT NULL, driver_id TEXT NOT NULL, bonus_cents BIGINT NOT NULL, awarded_ms BIGINT NOT NULL);

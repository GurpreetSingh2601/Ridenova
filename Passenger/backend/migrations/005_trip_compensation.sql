-- Additive Build 45: assignment-level compensation and auditable review/finalization.
CREATE TABLE IF NOT EXISTS engagements45(id TEXT PRIMARY KEY,ride_id TEXT NOT NULL,driver_id TEXT NOT NULL,start_ms BIGINT NOT NULL,end_ms BIGINT,payload TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS engagements45_driver ON engagements45(driver_id,start_ms);
CREATE INDEX IF NOT EXISTS engagements45_ride ON engagements45(ride_id);
CREATE TABLE IF NOT EXISTS pay_periods45(driver_id TEXT NOT NULL,period TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(driver_id,period));
CREATE TABLE IF NOT EXISTS pay_policy45(effective_date TEXT PRIMARY KEY,hourly_cents INTEGER NOT NULL,km_cents INTEGER NOT NULL,actor TEXT NOT NULL,reason TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS boost_reservations45(engagement_id TEXT PRIMARY KEY,zone_id TEXT NOT NULL,bonus_cents INTEGER NOT NULL,status TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS offer_snapshots45(driver_id TEXT NOT NULL,ride_id TEXT NOT NULL,expires_ms BIGINT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(driver_id,ride_id));

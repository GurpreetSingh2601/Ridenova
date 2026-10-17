-- Build 44 additive safety evidence. Existing migrations remain unchanged.

CREATE TABLE IF NOT EXISTS trip_evidence44(id TEXT PRIMARY KEY,ride_id TEXT NOT NULL,actor TEXT NOT NULL,kind TEXT NOT NULL,observed_ms BIGINT NOT NULL,received_ms BIGINT NOT NULL,payload TEXT NOT NULL,UNIQUE(ride_id,actor,kind,observed_ms));
CREATE INDEX IF NOT EXISTS evidence44_trip ON trip_evidence44(ride_id,observed_ms,id);
CREATE TABLE IF NOT EXISTS trip_monitor44(ride_id TEXT PRIMARY KEY,driver_id TEXT NOT NULL,state TEXT NOT NULL,opened_ms BIGINT NOT NULL,updated_ms BIGINT NOT NULL,best_km REAL NOT NULL,response TEXT NOT NULL,hold_until_ms BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS trip_consent44(ride_id TEXT PRIMARY KEY,owner TEXT NOT NULL,enabled INTEGER NOT NULL,updated_ms BIGINT NOT NULL);
CREATE TABLE IF NOT EXISTS trip_shares44(digest TEXT PRIMARY KEY,ride_id TEXT NOT NULL,owner TEXT NOT NULL,expires_ms BIGINT NOT NULL,revoked INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS trip_holds44(ride_id TEXT PRIMARY KEY,until_ms BIGINT NOT NULL,reason TEXT NOT NULL,actor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS driver_inbox44(id TEXT PRIMARY KEY,driver_id TEXT NOT NULL,kind TEXT NOT NULL,body TEXT NOT NULL,created_ms BIGINT NOT NULL,read_ms BIGINT);
CREATE INDEX IF NOT EXISTS inbox44_driver ON driver_inbox44(driver_id,created_ms);
CREATE TABLE IF NOT EXISTS document_versions44(id TEXT PRIMARY KEY,driver_id TEXT NOT NULL,kind TEXT NOT NULL,revision INTEGER NOT NULL,at_ms BIGINT NOT NULL,payload TEXT NOT NULL,content BYTEA,UNIQUE(driver_id,kind,revision));
CREATE TABLE IF NOT EXISTS operation_config44(name TEXT PRIMARY KEY,value TEXT NOT NULL);

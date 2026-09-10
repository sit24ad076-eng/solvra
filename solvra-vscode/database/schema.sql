-- SOLVRA local SQLite schema reference.
-- The FastAPI application creates these tables automatically on first run.
CREATE TABLE problems (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  domain TEXT NOT NULL,
  severity TEXT NOT NULL,
  urgency TEXT NOT NULL,
  latitude REAL NOT NULL,
  longitude REAL NOT NULL,
  address TEXT,
  district TEXT,
  status TEXT NOT NULL,
  people_affected INTEGER DEFAULT 0,
  ai_confidence REAL DEFAULT 0,
  created_at DATETIME,
  image_url TEXT
);
CREATE TABLE clusters (
  id TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  domain TEXT NOT NULL,
  problem_ids TEXT,
  confidence REAL DEFAULT 0,
  root_cause TEXT,
  recommended_action TEXT,
  created_at DATETIME
);
CREATE TABLE audit_logs (
  id TEXT PRIMARY KEY,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT,
  detail TEXT,
  created_at DATETIME
);

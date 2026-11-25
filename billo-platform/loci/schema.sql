-- ==============================================================================
-- LOCI & Billo Unified Database Schema (context2.db)
-- Enforces WAL concurrency, transaction integrity, and high-performance querying.
-- ==============================================================================

PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 5000;

-- 1. Temporal Decay Eras (3-tier decay: far, mid, near)
CREATE TABLE IF NOT EXISTS context_era (
    era_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    era_tier TEXT NOT NULL CHECK(era_tier IN ('far', 'mid', 'near')),
    start_turn INTEGER NOT NULL,
    end_turn INTEGER NOT NULL,
    summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_era_session ON context_era(session_id, era_tier);

-- 2. Context Structural Hierarchy
CREATE TABLE IF NOT EXISTS context_hierarchy (
    node_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    parent_id TEXT,
    title TEXT NOT NULL,
    level INTEGER DEFAULT 0,
    metadata_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(parent_id) REFERENCES context_hierarchy(node_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_hierarchy_session ON context_hierarchy(session_id, parent_id);

-- 3. Extracted Context Entities & Ring Buffers
CREATE TABLE IF NOT EXISTS context_entities (
    key_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    entity_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    era_id TEXT,
    hit_count INTEGER DEFAULT 1,
    is_symlink INTEGER DEFAULT 0,
    tags_json TEXT,
    occurrences_json TEXT,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (session_id, entity_name),
    FOREIGN KEY(era_id) REFERENCES context_era(era_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_entities_lookup ON context_entities(session_id, entity_type, hit_count DESC);
CREATE INDEX IF NOT EXISTS idx_entities_key ON context_entities(key_id);

-- 4. Token Efficiency Audit Log (Resolves Bug #10 with WAL)
CREATE TABLE IF NOT EXISTS token_efficiency_log (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    key_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    raw_entities_scanned INTEGER NOT NULL,
    hits_returned INTEGER NOT NULL,
    loci_tokens REAL NOT NULL,
    baseline_tokens REAL NOT NULL,
    cer_ratio REAL NOT NULL,
    grade TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_eff_session ON token_efficiency_log(session_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_eff_query ON token_efficiency_log(query_hash);

-- 5. Context Compression Ledger
CREATE TABLE IF NOT EXISTS compress_log (
    compress_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    tokens_before INTEGER NOT NULL,
    tokens_after INTEGER NOT NULL,
    tokens_saved INTEGER NOT NULL,
    credits_saved_usd REAL NOT NULL DEFAULT 0.0,
    discrepancy_pct REAL DEFAULT 0.0,
    method TEXT DEFAULT 'vps_ollama_3b',
    vps_ok INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_compress_session ON compress_log(session_id, created_at DESC);

-- 6. Task Queue for Background Workers
CREATE TABLE IF NOT EXISTS task_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result TEXT,
    error TEXT,
    retries INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_task_queue_status ON task_queue(status, id ASC);

-- 7. Scratch Key-Value Store
CREATE TABLE IF NOT EXISTS scratch_data (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 8. GPU Workstation Tracking Tables
CREATE TABLE IF NOT EXISTS image_runs (
    run_id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    status TEXT NOT NULL,
    result_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS forge_sessions (
    session_id TEXT PRIMARY KEY,
    target_file TEXT,
    status TEXT NOT NULL,
    patch_summary TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

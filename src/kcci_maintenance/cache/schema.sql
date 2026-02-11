-- ============================================================================
-- GEOCODE CACHE SCHEMA v1.0
-- ============================================================================
-- Purpose: Store geocoded 811 tickets with versioning and quality metadata
-- Author: Corey Klaasmeyer / Claude Code
-- Date: 2026-02-08
-- ============================================================================

CREATE TABLE IF NOT EXISTS geocode_cache (
    -- Primary key
    cache_id INTEGER PRIMARY KEY AUTOINCREMENT,
    
    -- Ticket identification
    ticket_number TEXT NOT NULL,
    geocode_key TEXT NOT NULL,  -- SHA256 of (street||intersection||city||county)
    
    -- Input data (for reprocessing decisions and context)
    street TEXT,
    intersection TEXT,
    city TEXT,
    county TEXT,
    ticket_type TEXT,          -- Emergency, Normal, Update, Survey/Design
    duration TEXT,             -- 1 DAY, 2 MONTHS, etc.
    work_type TEXT,            -- Hydro-excavation, Pipeline Maintenance, etc.
    excavator TEXT,            -- Company name
    
    -- Geocoding result
    latitude REAL,
    longitude REAL,
    method TEXT NOT NULL,      -- API_PRIMARY, GEOMETRIC_INTERSECTION, PROXIMITY_BASED, MANUAL
    approach TEXT,             -- closest_point, corridor_midpoint, city_centroid_fallback
    confidence REAL,           -- 0.0 to 1.0
    reasoning TEXT,            -- Human-readable explanation
    error_message TEXT,        -- If geocoding failed
    
    -- Quality metadata
    quality_tier TEXT NOT NULL CHECK(quality_tier IN (
        'EXCELLENT', 'GOOD', 'ACCEPTABLE', 'REVIEW_NEEDED', 'FAILED'
    )),
    review_priority TEXT CHECK(review_priority IN (
        'NONE', 'LOW', 'MEDIUM', 'HIGH', 'CRITICAL'
    )),
    validation_flags TEXT,     -- JSON array: ["low_confidence", "distance_from_city"]
    
    -- Version tracking
    version INTEGER NOT NULL DEFAULT 1,
    supersedes_cache_id INTEGER REFERENCES geocode_cache(cache_id),
    is_current BOOLEAN NOT NULL DEFAULT 1,  -- Only one current version per ticket
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by_stage TEXT NOT NULL,  -- stage_1_api, stage_3_proximity, human_review
    
    -- Reprocessing control
    locked BOOLEAN NOT NULL DEFAULT 0,  -- If 1, don't reprocess (human verified)
    lock_reason TEXT,          -- "Human verified with ROW map"
    locked_at TIMESTAMP,
    locked_by TEXT,            -- Username or "human_review"
    
    -- Full metadata (JSON)
    metadata_json TEXT,        -- Complete metadata as JSON for extensibility
    
    -- Performance tracking
    processing_time_ms INTEGER,  -- How long this geocoding took
    
    -- Constraints
    UNIQUE(ticket_number, version),
    CHECK(latitude IS NULL OR (latitude >= -90 AND latitude <= 90)),
    CHECK(longitude IS NULL OR (longitude >= -180 AND longitude <= 180)),
    CHECK(confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ticket_number ON geocode_cache(ticket_number);
CREATE INDEX IF NOT EXISTS idx_geocode_key ON geocode_cache(geocode_key);
CREATE INDEX IF NOT EXISTS idx_quality_tier ON geocode_cache(quality_tier);
CREATE INDEX IF NOT EXISTS idx_review_priority ON geocode_cache(review_priority);
CREATE INDEX IF NOT EXISTS idx_is_current ON geocode_cache(is_current);
CREATE INDEX IF NOT EXISTS idx_locked ON geocode_cache(locked);
CREATE INDEX IF NOT EXISTS idx_created_at ON geocode_cache(created_at);

-- ============================================================================
-- PIPELINE EXECUTION HISTORY
-- ============================================================================

CREATE TABLE IF NOT EXISTS pipeline_history (
    run_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Pipeline metadata
    pipeline_version TEXT,
    config_hash TEXT,          -- SHA256 of config file for reproducibility
    
    -- Execution summary
    total_tickets INTEGER NOT NULL,
    tickets_processed INTEGER NOT NULL,
    tickets_skipped INTEGER NOT NULL,
    tickets_cached INTEGER NOT NULL,
    tickets_improved INTEGER NOT NULL,  -- Quality tier increased
    tickets_degraded INTEGER NOT NULL,  -- Quality tier decreased (shouldn't happen!)
    
    -- Quality breakdown
    excellent_count INTEGER,
    good_count INTEGER,
    acceptable_count INTEGER,
    review_needed_count INTEGER,
    failed_count INTEGER,
    
    -- Performance
    total_runtime_seconds REAL,
    avg_processing_time_ms REAL,
    
    -- Stage-specific results
    stage_results TEXT,        -- JSON: {stage_name: {processed, skipped, improved}}
    
    -- Configuration snapshot
    config_json TEXT,          -- Full config at time of run
    
    -- Notes
    notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_run_timestamp ON pipeline_history(run_timestamp);

-- ============================================================================
-- HUMAN REVIEWS
-- ============================================================================

CREATE TABLE IF NOT EXISTS human_reviews (
    review_id INTEGER PRIMARY KEY AUTOINCREMENT,
    cache_id INTEGER NOT NULL REFERENCES geocode_cache(cache_id),
    ticket_number TEXT NOT NULL,
    
    -- Review metadata
    reviewer TEXT NOT NULL,
    reviewed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    review_action TEXT NOT NULL CHECK(review_action IN (
        'APPROVED',           -- Accept current location
        'CORRECTED',          -- Override with new coordinates
        'FLAGGED',            -- Needs more investigation
        'DEFERRED',           -- Review later
        'INVALID_TICKET'      -- Ticket data is bad
    )),
    
    -- Corrections (if action = CORRECTED)
    corrected_latitude REAL,
    corrected_longitude REAL,
    correction_source TEXT,    -- "PLAINS ROW map", "Field verification", "Manual research"
    correction_method TEXT,    -- How they found the correction
    
    -- Review context
    time_spent_seconds INTEGER,  -- How long review took
    confidence_in_review REAL,   -- Reviewer's confidence (0-1)
    notes TEXT,
    
    -- For tracking patterns
    original_confidence REAL,
    original_quality_tier TEXT,
    
    CHECK(corrected_latitude IS NULL OR (corrected_latitude >= -90 AND corrected_latitude <= 90)),
    CHECK(corrected_longitude IS NULL OR (corrected_longitude >= -180 AND corrected_longitude <= 180))
);

CREATE INDEX IF NOT EXISTS idx_review_ticket ON human_reviews(ticket_number);
CREATE INDEX IF NOT EXISTS idx_review_action ON human_reviews(review_action);
CREATE INDEX IF NOT EXISTS idx_reviewed_at ON human_reviews(reviewed_at);

-- ============================================================================
-- IMPROVEMENT TRACKING VIEW
-- ============================================================================

CREATE VIEW IF NOT EXISTS improvement_tracking AS
SELECT 
    new.ticket_number,
    new.cache_id as new_cache_id,
    old.cache_id as old_cache_id,
    old.version as old_version,
    new.version as new_version,
    old.confidence as old_confidence,
    new.confidence as new_confidence,
    (new.confidence - old.confidence) as confidence_delta,
    old.quality_tier as old_quality_tier,
    new.quality_tier as new_quality_tier,
    old.created_at as old_timestamp,
    new.created_at as new_timestamp,
    old.created_by_stage as old_stage,
    new.created_by_stage as new_stage,
    CASE
        WHEN old.quality_tier = 'FAILED' AND new.quality_tier != 'FAILED' THEN 'failure_resolved'
        WHEN old.quality_tier = 'REVIEW_NEEDED' AND new.quality_tier IN ('ACCEPTABLE', 'GOOD', 'EXCELLENT') THEN 'quality_improved'
        WHEN old.quality_tier = 'ACCEPTABLE' AND new.quality_tier IN ('GOOD', 'EXCELLENT') THEN 'quality_improved'
        WHEN old.quality_tier = 'GOOD' AND new.quality_tier = 'EXCELLENT' THEN 'quality_improved'
        ELSE 'no_improvement'
    END as improvement_type
FROM geocode_cache old
INNER JOIN geocode_cache new ON new.supersedes_cache_id = old.cache_id
WHERE new.is_current = 1;

-- ============================================================================
-- SCHEMA VERSION TRACKING
-- ============================================================================

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    description TEXT
);

INSERT OR IGNORE INTO schema_version (version, description) VALUES (1, 'Initial schema');

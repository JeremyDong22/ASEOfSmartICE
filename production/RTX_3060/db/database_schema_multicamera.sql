-- Multi-Camera Restaurant Monitoring Database Schema
-- Version: 2.0.0
-- Last Updated: 2025-11-14
--
-- Purpose: Support multiple cameras per location with comprehensive state tracking
-- Features: Multi-location support, video management, ROI configurations, state tracking

-- =============================================================================
-- CORE ENTITY TABLES
-- =============================================================================

-- LOCATIONS: Restaurant locations/stores
CREATE TABLE IF NOT EXISTS locations (
    location_id TEXT PRIMARY KEY,
    location_name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    region TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active INTEGER DEFAULT 1
);

-- CAMERAS: Individual camera hardware
CREATE TABLE IF NOT EXISTS cameras (
    camera_id TEXT PRIMARY KEY,
    location_id TEXT NOT NULL,
    camera_name TEXT,
    camera_ip_address TEXT,
    rtsp_endpoint TEXT,
    camera_type TEXT DEFAULT 'UNV',
    resolution TEXT,
    installation_date TEXT,
    division_name TEXT,
    division_description TEXT,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (location_id) REFERENCES locations(location_id),
    UNIQUE(camera_ip_address)
);

-- CAMERA_ROIS: ROI configurations per camera
CREATE TABLE IF NOT EXISTS camera_rois (
    roi_id INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id TEXT NOT NULL,
    roi_type TEXT NOT NULL,  -- 'division', 'table', 'sitting', 'service'
    roi_identifier TEXT NOT NULL,  -- e.g., "T1", "SA1", "SV1"
    polygon_points TEXT NOT NULL,  -- JSON array of [x, y] coordinates
    linked_to_roi_id TEXT,  -- For sitting areas linked to tables
    description TEXT,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id),
    UNIQUE(camera_id, roi_identifier)
);

-- =============================================================================
-- VIDEO & SESSION MANAGEMENT
-- =============================================================================

-- VIDEOS: Track all video files per camera
CREATE TABLE IF NOT EXISTS videos (
    video_id INTEGER PRIMARY KEY AUTOINCREMENT,
    camera_id TEXT NOT NULL,
    video_filename TEXT NOT NULL,  -- e.g., "camera_35_20251114_183000.mp4"
    video_path TEXT,
    video_date TEXT NOT NULL,  -- YYYY-MM-DD format
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    duration_seconds INTEGER,
    file_size_bytes INTEGER,
    fps REAL,
    resolution TEXT,
    is_processed INTEGER DEFAULT 0,
    storage_location TEXT DEFAULT 'local',  -- 'local', 'cloud', 'archive'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id)
);

-- SESSIONS: Processing sessions linking camera, video, and analysis
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    camera_id TEXT NOT NULL,
    video_id INTEGER NOT NULL,
    location_id TEXT NOT NULL,
    config_file_path TEXT,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    total_frames INTEGER,
    fps REAL,
    resolution TEXT,
    processing_status TEXT DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    processing_time_seconds REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id),
    FOREIGN KEY (video_id) REFERENCES videos(video_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

-- =============================================================================
-- STATE TRACKING TABLES
-- =============================================================================

-- DIVISION_STATES: Division/area state changes per camera
CREATE TABLE IF NOT EXISTS division_states (
    division_state_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    frame_number INTEGER NOT NULL,
    timestamp_video REAL NOT NULL,  -- Video timestamp in seconds
    timestamp_recorded TIMESTAMP NOT NULL,  -- Wall clock time
    state TEXT NOT NULL,  -- 'RED', 'YELLOW', 'GREEN'
    walking_area_waiters INTEGER,
    service_area_waiters INTEGER,
    total_staff INTEGER,
    screenshot_path TEXT,
    screenshot_url TEXT,  -- Cloud URL if uploaded
    confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

-- TABLE_STATES: Table state changes per camera
CREATE TABLE IF NOT EXISTS table_states (
    table_state_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    camera_id TEXT NOT NULL,
    location_id TEXT NOT NULL,
    frame_number INTEGER NOT NULL,
    timestamp_video REAL NOT NULL,  -- Video timestamp in seconds
    timestamp_recorded TIMESTAMP NOT NULL,  -- Wall clock time
    table_id TEXT NOT NULL,  -- e.g., "T1"
    state TEXT NOT NULL,  -- 'IDLE', 'BUSY', 'CLEANING'
    customers_count INTEGER,
    waiters_count INTEGER,
    screenshot_path TEXT,
    screenshot_url TEXT,  -- Cloud URL if uploaded
    confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id),
    FOREIGN KEY (camera_id) REFERENCES cameras(camera_id),
    FOREIGN KEY (location_id) REFERENCES locations(location_id)
);

-- =============================================================================
-- SUPPORTING TABLES
-- =============================================================================

-- PROCESSING_LOGS: Track processing errors and warnings
CREATE TABLE IF NOT EXISTS processing_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    camera_id TEXT NOT NULL,
    log_level TEXT,  -- 'INFO', 'WARNING', 'ERROR'
    message TEXT,
    frame_number INTEGER,
    details TEXT,  -- JSON string for additional details
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================

-- Videos indexes
CREATE INDEX IF NOT EXISTS idx_videos_camera_date ON videos(camera_id, video_date);
CREATE INDEX IF NOT EXISTS idx_videos_unprocessed ON videos(camera_id, is_processed) WHERE is_processed = 0;

-- Sessions indexes
CREATE INDEX IF NOT EXISTS idx_sessions_camera ON sessions(camera_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_location ON sessions(location_id, created_at);
CREATE INDEX IF NOT EXISTS idx_sessions_video ON sessions(video_id);

-- Division states indexes
CREATE INDEX IF NOT EXISTS idx_division_session_frame ON division_states(session_id, frame_number);
CREATE INDEX IF NOT EXISTS idx_division_camera_time ON division_states(camera_id, timestamp_recorded DESC);
CREATE INDEX IF NOT EXISTS idx_division_location_time ON division_states(location_id, timestamp_recorded DESC);
CREATE INDEX IF NOT EXISTS idx_division_state ON division_states(state);

-- Table states indexes
CREATE INDEX IF NOT EXISTS idx_table_session_frame ON table_states(session_id, frame_number);
CREATE INDEX IF NOT EXISTS idx_table_camera_time ON table_states(camera_id, timestamp_recorded DESC);
CREATE INDEX IF NOT EXISTS idx_table_location_time ON table_states(location_id, timestamp_recorded DESC);
CREATE INDEX IF NOT EXISTS idx_table_location_table ON table_states(location_id, table_id, timestamp_recorded DESC);
CREATE INDEX IF NOT EXISTS idx_table_state ON table_states(state);

-- Processing logs indexes
CREATE INDEX IF NOT EXISTS idx_logs_session ON processing_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_logs_camera ON processing_logs(camera_id, created_at);

-- Camera ROIs indexes
CREATE INDEX IF NOT EXISTS idx_camera_roi_type ON camera_rois(camera_id, roi_type);

-- =============================================================================
-- INITIAL DATA
-- =============================================================================

-- Insert default location
INSERT OR IGNORE INTO locations (location_id, location_name, city, region)
VALUES ('ybl_mianyang', 'Ye Bai Ling Hotpot - Mianyang', 'Mianyang', 'Sichuan');

-- Insert default cameras
INSERT OR IGNORE INTO cameras (camera_id, location_id, camera_name, camera_ip_address,
                               division_name, resolution, status)
VALUES
    ('camera_35', 'ybl_mianyang', 'Front Area Camera', '202.168.40.35',
     'A区', '2592x1944', 'active'),
    ('camera_22', 'ybl_mianyang', 'Service Area Camera', '202.168.40.22',
     'B区', '2592x1944', 'active');

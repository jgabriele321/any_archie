-- Migration: Add heartbeat_state table for proactive monitoring
-- This enables per-user heartbeat notifications for emails, tasks, and calendar events

CREATE TABLE IF NOT EXISTS heartbeat_state (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    last_heartbeat TIMESTAMP,
    muted_until TIMESTAMP,
    last_notified_email_ids TEXT[],  -- Array of email IDs we've notified about
    last_notified_task_hashes TEXT[],  -- Array of task hashes we've notified about
    last_notified_calendar_ids TEXT[],  -- Array of calendar event IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_heartbeat_state_user_id ON heartbeat_state(user_id);
CREATE INDEX IF NOT EXISTS idx_heartbeat_state_muted ON heartbeat_state(muted_until) WHERE muted_until IS NOT NULL;
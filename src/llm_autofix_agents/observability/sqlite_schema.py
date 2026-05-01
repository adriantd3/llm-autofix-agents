from __future__ import annotations

SCHEMA_VERSION = 4

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS architectures (
  architecture_id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT
);

CREATE TABLE IF NOT EXISTS model_configs (
  model_config_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  base_url TEXT,
  max_turns INTEGER,
  tracing_disabled INTEGER,
  extra_json TEXT,
  UNIQUE (provider, model, base_url, max_turns, tracing_disabled, extra_json)
);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  architecture_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  target_repo TEXT,
  target_branch TEXT,
  benchmark_name TEXT,
  problem_id TEXT,
  prompt_hash TEXT,
  run_fingerprint TEXT,
  final_status TEXT,
  stop_reason TEXT,
  resolved INTEGER NOT NULL DEFAULT 0,
  duration_seconds REAL,
  total_iterations INTEGER NOT NULL DEFAULT 0,
  total_input_tokens INTEGER NOT NULL DEFAULT 0,
  total_output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  files_changed_count INTEGER NOT NULL DEFAULT 0,
  live_log_path TEXT,
  summary_path TEXT,
  diff_path TEXT,
  FOREIGN KEY (architecture_id) REFERENCES architectures(architecture_id)
);

CREATE TABLE IF NOT EXISTS run_agents (
  run_agent_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent_name TEXT NOT NULL,
  agent_role TEXT NOT NULL,
  agent_order INTEGER,
  model_config_id TEXT NOT NULL,
  instructions_hash TEXT,
  tool_profile TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (model_config_id) REFERENCES model_configs(model_config_id),
  UNIQUE (run_id, agent_name)
);

CREATE TABLE IF NOT EXISTS iterations (
  iteration_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_index INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  duration_seconds REAL,
  status TEXT,
  stop_reason TEXT,
  repo_changed INTEGER NOT NULL DEFAULT 0,
  changed_files_count INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  tool_calls_count INTEGER NOT NULL DEFAULT 0,
  test_exit_code INTEGER,
  test_timed_out INTEGER,
  test_signature TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  UNIQUE (run_id, iteration_index)
);

CREATE TABLE IF NOT EXISTS agent_executions (
  agent_execution_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT NOT NULL,
  run_agent_id TEXT NOT NULL,
  execution_index INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  duration_seconds REAL,
  status TEXT,
  reasoning_summary TEXT,
  confidence REAL,
  notes TEXT,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  tool_calls_count INTEGER NOT NULL DEFAULT 0,
  error_type TEXT,
  error_message_short TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
  FOREIGN KEY (run_agent_id) REFERENCES run_agents(run_agent_id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
  tool_call_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT NOT NULL,
  agent_execution_id TEXT,
  seq INTEGER NOT NULL,
  tool_name TEXT NOT NULL,
  status TEXT,
  success INTEGER,
  agent_name TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
  FOREIGN KEY (agent_execution_id) REFERENCES agent_executions(agent_execution_id)
);

CREATE TABLE IF NOT EXISTS provider_call_events (
  provider_call_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT NOT NULL,
  agent_execution_id TEXT,
  event_type TEXT NOT NULL,
  attempt INTEGER NOT NULL,
  total_attempts INTEGER NOT NULL,
  status_code INTEGER,
  error_type TEXT,
  error_message_short TEXT,
  tool_calls_count INTEGER,
  retry_delay_seconds REAL,
  rerun_full_runner INTEGER NOT NULL DEFAULT 1,
  occurred_at TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
  FOREIGN KEY (agent_execution_id) REFERENCES agent_executions(agent_execution_id)
);

CREATE TABLE IF NOT EXISTS test_executions (
  test_execution_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT,
  agent_execution_id TEXT,
  tool_call_id TEXT,
  phase TEXT NOT NULL,
  command TEXT,
  duration_seconds REAL,
  exit_code INTEGER,
  timed_out INTEGER,
  signature TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
  FOREIGN KEY (agent_execution_id) REFERENCES agent_executions(agent_execution_id),
  FOREIGN KEY (tool_call_id) REFERENCES tool_calls(tool_call_id)
);

CREATE TABLE IF NOT EXISTS file_changes (
  file_change_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT,
  agent_execution_id TEXT,
  tool_call_id TEXT,
  path TEXT NOT NULL,
  change_type TEXT,
  additions INTEGER,
  deletions INTEGER,
  detected_by TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
  FOREIGN KEY (agent_execution_id) REFERENCES agent_executions(agent_execution_id),
  FOREIGN KEY (tool_call_id) REFERENCES tool_calls(tool_call_id)
);

CREATE INDEX IF NOT EXISTS idx_runs_architecture ON runs(architecture_id);
CREATE INDEX IF NOT EXISTS idx_iterations_run ON iterations(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_run_agent ON agent_executions(run_agent_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_name ON tool_calls(tool_name);
CREATE INDEX IF NOT EXISTS idx_provider_call_events_run ON provider_call_events(run_id);
CREATE INDEX IF NOT EXISTS idx_provider_call_events_agent_execution ON provider_call_events(agent_execution_id);

CREATE TABLE IF NOT EXISTS agent_handoffs (
  handoff_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT,
  from_agent_name TEXT NOT NULL,
  to_agent_name TEXT NOT NULL,
  from_run_agent_id TEXT,
  to_run_agent_id TEXT,
  occurred_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id)
);

CREATE INDEX IF NOT EXISTS idx_agent_handoffs_run ON agent_handoffs(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_handoffs_iteration ON agent_handoffs(iteration_id);
"""


MIGRATION_V3_TO_V4 = """
ALTER TABLE tool_calls ADD COLUMN agent_name TEXT;
CREATE TABLE IF NOT EXISTS agent_handoffs (
  handoff_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT,
  from_agent_name TEXT NOT NULL,
  to_agent_name TEXT NOT NULL,
  from_run_agent_id TEXT,
  to_run_agent_id TEXT,
  occurred_at TEXT NOT NULL,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id)
);
CREATE INDEX IF NOT EXISTS idx_agent_handoffs_run ON agent_handoffs(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_handoffs_iteration ON agent_handoffs(iteration_id);
"""


def schema_init_sql() -> str:
    return SCHEMA_SQL

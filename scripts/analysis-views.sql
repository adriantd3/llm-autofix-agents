-- =============================================================================
-- TFM Analysis Views — reference script
-- =============================================================================
-- These views are created automatically when you run:
--
--   uv run autofix validate --batch-dir <path> --create-views
--
-- Or manually on any aggregate DB:
--
--   sqlite3 results/analysis.db < scripts/analysis-views.sql
--
-- The views expect a DB produced by the aggregator (observability.aggregate)
-- that contains a `batch_id` column on `runs` and a populated `run_validations`
-- table from the validator (autofix validate).
-- =============================================================================

-- v_run_summary: one row per run with all metadata + validation verdict.
CREATE VIEW IF NOT EXISTS v_run_summary AS
SELECT
  r.run_id,
  r.benchmark_name,
  r.problem_id,
  a.name            AS architecture,
  mc.model,
  mc.provider,
  r.final_status,
  r.resolved,
  r.total_iterations,
  r.total_tokens,
  r.total_input_tokens,
  r.total_output_tokens,
  r.duration_seconds,
  r.files_changed_count,
  r.started_at,
  r.batch_id,
  v.verdict,
  v.confidence,
  v.test_passed,
  v.infra_fail_detected,
  v.canonical_patch_available,
  v.patch_semantically_matches,
  v.justification,
  v.validated_at
FROM runs r
JOIN architectures a USING (architecture_id)
LEFT JOIN run_agents ra ON ra.run_id = r.run_id AND ra.agent_order = 1
LEFT JOIN model_configs mc ON mc.model_config_id = ra.model_config_id
LEFT JOIN run_validations v USING (run_id);

-- v_architecture_metrics: aggregated repair/plausible rates per architecture×model×benchmark.
-- Only includes runs with a verdict (INFRA_FAIL counts as a run but not as plausible/correct).
CREATE VIEW IF NOT EXISTS v_architecture_metrics AS
SELECT
  a.name        AS architecture,
  mc.model,
  r.benchmark_name,
  COUNT(*)      AS total_runs,
  SUM(CASE WHEN v.verdict = 'CORRECT' THEN 1 ELSE 0 END)
                AS correct,
  SUM(CASE WHEN v.verdict IN ('CORRECT', 'PLAUSIBLE') THEN 1 ELSE 0 END)
                AS plausible,
  ROUND(1.0 * SUM(CASE WHEN v.verdict = 'CORRECT' THEN 1 ELSE 0 END) / COUNT(*), 3)
                AS repair_rate,
  ROUND(1.0 * SUM(CASE WHEN v.verdict IN ('CORRECT', 'PLAUSIBLE') THEN 1 ELSE 0 END) / COUNT(*), 3)
                AS plausible_rate,
  ROUND(AVG(r.total_tokens), 0)
                AS avg_tokens,
  ROUND(AVG(r.total_iterations), 2)
                AS avg_iterations
FROM runs r
JOIN architectures a USING (architecture_id)
LEFT JOIN run_agents ra ON ra.run_id = r.run_id AND ra.agent_order = 1
LEFT JOIN model_configs mc ON mc.model_config_id = ra.model_config_id
LEFT JOIN run_validations v USING (run_id)
WHERE v.verdict IS NOT NULL
GROUP BY a.name, mc.model, r.benchmark_name;

-- v_bug_heatmap: per-bug matrix suitable for a heatmap table in the TFM.
-- ever_correct / ever_plausible flags allow Pass@k-style analysis when
-- multiple runs per bug exist.
CREATE VIEW IF NOT EXISTS v_bug_heatmap AS
SELECT
  r.problem_id  AS bug,
  r.benchmark_name,
  a.name        AS architecture,
  mc.model,
  COUNT(*)      AS total_runs,
  GROUP_CONCAT(COALESCE(v.verdict, 'UNVALIDATED'), ', ')
                AS verdicts,
  MAX(CASE WHEN v.verdict = 'CORRECT' THEN 1 ELSE 0 END)
                AS ever_correct,
  MAX(CASE WHEN v.verdict IN ('CORRECT', 'PLAUSIBLE') THEN 1 ELSE 0 END)
                AS ever_plausible
FROM runs r
JOIN architectures a USING (architecture_id)
LEFT JOIN run_agents ra ON ra.run_id = r.run_id AND ra.agent_order = 1
LEFT JOIN model_configs mc ON mc.model_config_id = ra.model_config_id
LEFT JOIN run_validations v USING (run_id)
GROUP BY r.problem_id, r.benchmark_name, a.name, mc.model;

-- =============================================================================
-- Example queries for TFM analysis
-- =============================================================================

-- Architecture comparison table:
-- SELECT architecture, model, benchmark_name, repair_rate, plausible_rate,
--        avg_tokens, avg_iterations
-- FROM v_architecture_metrics
-- ORDER BY repair_rate DESC;

-- Per-bug heatmap (for a single benchmark):
-- SELECT bug, architecture, model, verdicts, ever_correct
-- FROM v_bug_heatmap
-- WHERE benchmark_name = 'bugsinpy'
-- ORDER BY bug, architecture;

-- Overfitting gap (plausible_rate - repair_rate) per architecture:
-- SELECT architecture, model, benchmark_name,
--        repair_rate, plausible_rate,
--        ROUND(plausible_rate - repair_rate, 3) AS overfit_gap
-- FROM v_architecture_metrics
-- ORDER BY overfit_gap DESC;

-- Token efficiency vs. repair quality:
-- SELECT architecture, model, repair_rate, avg_tokens
-- FROM v_architecture_metrics
-- ORDER BY benchmark_name, repair_rate DESC;

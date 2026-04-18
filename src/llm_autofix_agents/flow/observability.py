from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from os import getenv
from pathlib import Path
from typing import Any

from llm_autofix_agents.contracts import RunMetrics, RunObservabilityRecord, RunOutput, ToolCallTrace

logger = logging.getLogger(__name__)


def build_run_metrics(
    *,
    output: RunOutput,
    iterations: int,
    duration_seconds: float,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    metadata: dict[str, Any],
) -> RunMetrics:
    cost_per_1k_tokens = _resolve_cost_per_1k_tokens(metadata)
    if cost_per_1k_tokens is None:
        estimated_cost_usd = 0.0
        cost_source = "missing_rate"
    else:
        estimated_cost_usd = (total_tokens / 1000.0) * cost_per_1k_tokens
        cost_source = "metadata_cost_per_1k_tokens_usd"

    return RunMetrics(
        success=output.status.value == "success",
        iterations=iterations,
        duration_seconds=duration_seconds,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        cost_source=cost_source,
    )


def build_observability_record(
    *,
    output: RunOutput,
    metrics: RunMetrics,
    tool_calls: list[ToolCallTrace],
) -> RunObservabilityRecord:
    return RunObservabilityRecord(
        run_id=output.identity.run_id,
        run_fingerprint=output.identity.run_fingerprint,
        iteration_id=output.identity.iteration_id,
        status=output.status,
        stop_reason=output.stop_reason,
        metrics=metrics,
        tool_calls=tool_calls,
        artifacts=output.artifacts,
        timestamp=datetime.now(UTC).isoformat(),
    )


def persist_observability_record(
    *,
    repo_root: Path,
    record: RunObservabilityRecord,
) -> dict[str, Any]:
    mongo_uri = getenv("MONGODB_CONNECTION_URL") or getenv("MONGODB_ATLAS_URI")
    mongo_database = getenv("MONGODB_DATABASE", "llm_autofix_agents")
    mongo_collection = getenv("MONGODB_COLLECTION", "run_results")

    if mongo_uri:
        try:
            _persist_to_mongodb(
                mongo_uri=mongo_uri,
                database=mongo_database,
                collection=mongo_collection,
                record=record,
            )
            logger.info(
                "observability persisted to mongodb db=%s collection=%s run_id=%s",
                mongo_database,
                mongo_collection,
                record.run_id,
            )
            return {
                "backend": "mongodb",
                "database": mongo_database,
                "collection": mongo_collection,
            }
        except Exception as exc:
            logger.warning(
                "mongodb persistence failed for run_id=%s, falling back to jsonl: %s",
                record.run_id,
                exc,
            )
            fallback_payload = _persist_to_jsonl(repo_root=repo_root, record=record)
            fallback_payload["fallback_reason"] = str(exc)
            return fallback_payload

    return _persist_to_jsonl(repo_root=repo_root, record=record)


def _resolve_cost_per_1k_tokens(metadata: dict[str, Any]) -> float | None:
    raw = metadata.get("cost_per_1k_tokens_usd")
    if raw is None:
        return None
    if isinstance(raw, int):
        if raw < 0:
            return None
        return float(raw)
    if isinstance(raw, float):
        if raw < 0.0:
            return None
        return raw
    return None


def _persist_to_mongodb(
    *,
    mongo_uri: str,
    database: str,
    collection: str,
    record: RunObservabilityRecord,
) -> None:
    from pymongo import MongoClient  # type: ignore[import-not-found]

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=3000)
    try:
        client.admin.command("ping")
        collection_ref = client[database][collection]
        payload = record.model_dump(mode="json")
        collection_ref.replace_one({"run_id": record.run_id}, payload, upsert=True)
    finally:
        client.close()


def _persist_to_jsonl(*, repo_root: Path, record: RunObservabilityRecord) -> dict[str, Any]:
    output_dir = repo_root / "results" / record.run_id
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "result.jsonl"

    with output_path.open("a", encoding="utf-8") as handler:
        handler.write(json.dumps(record.model_dump(mode="json"), ensure_ascii=True))
        handler.write("\n")

    logger.info("observability persisted to jsonl path=%s", output_path)
    return {
        "backend": "jsonl",
        "path": output_path.relative_to(repo_root).as_posix(),
    }

from llm_autofix_agents.flow.lifecycle.telemetry_mapping import to_file_change_telemetry_set
from llm_autofix_agents.flow.models import WorkspaceChangeSet
from llm_autofix_agents.llm.provider_events import ProviderCallEvent
from llm_autofix_agents.observability.telemetry import RunTelemetry
from llm_autofix_agents.observability.telemetry_models import FileChangeTelemetrySet


class FakeObserver:
    def __init__(self) -> None:
        self.test_records = []
        self.file_change_records = []
        self.agent_execution_started = []
        self.agent_execution_finished = []
        self.iteration_started = []
        self.provider_call_records = []

    def on_test_execution(self, *, record):
        self.test_records.append(record)

    def on_file_change(self, *, record):
        self.file_change_records.append(record)

    def on_agent_execution_started(self, *, record):
        self.agent_execution_started.append(record)

    def on_agent_execution_finished(self, *, record):
        self.agent_execution_finished.append(record)

    def on_iteration_started(self, *, record):
        self.iteration_started.append(record)

    def on_provider_call_event(self, *, record):
        self.provider_call_records.append(record)


def test_file_change_telemetry_set_registers_correct_types() -> None:
    changes = WorkspaceChangeSet(
        modified_files=["a.py", "b.py"],
        added_files=["c.py"],
        deleted_files=["d.py"],
        untracked_files=["e.py"],
        diff="",
        diff_excludes_untracked=False,
    )
    telemetry_set = to_file_change_telemetry_set(changes)

    assert telemetry_set.modified_files == ["a.py", "b.py"]
    assert telemetry_set.added_files == ["c.py"]
    assert telemetry_set.deleted_files == ["d.py"]
    assert telemetry_set.untracked_files == ["e.py"]


def test_iteration_telemetry_records_file_changes_with_correct_types() -> None:
    observer = FakeObserver()
    run_telemetry = RunTelemetry(observer=observer, run_id="run-1")
    iteration_telemetry = run_telemetry.start_iteration(iteration_id="it-1", iteration_index=1)

    telemetry_set = FileChangeTelemetrySet(
        modified_files=["a.py"],
        added_files=["new.py"],
        deleted_files=["deleted.py"],
        untracked_files=["untracked.py"],
    )
    iteration_telemetry.record_file_changes(
        agent_execution_id="agent-1",
        changes=telemetry_set,
    )

    types_by_path = {r.path: r.change_type for r in observer.file_change_records}
    assert types_by_path["a.py"] == "modified"
    assert types_by_path["new.py"] == "added"
    assert types_by_path["deleted.py"] == "deleted"
    assert types_by_path["untracked.py"] == "untracked"


def test_agent_execution_telemetry_create_hooks() -> None:
    observer = FakeObserver()
    run_telemetry = RunTelemetry(observer=observer, run_id="run-1")
    iteration_telemetry = run_telemetry.start_iteration(iteration_id="it-1", iteration_index=1)
    agent_telemetry = iteration_telemetry.start_agent_execution(
        run_agent_id="ra-1",
        execution_index=1,
    )

    hooks = agent_telemetry.create_hooks()

    assert hooks._run_id == "run-1"
    assert hooks._iteration_id == "it-1"
    assert hooks._agent_execution_id == agent_telemetry.agent_execution_id


def test_agent_execution_telemetry_finish_failed_records_error_details() -> None:
    observer = FakeObserver()
    run_telemetry = RunTelemetry(observer=observer, run_id="run-1")
    iteration_telemetry = run_telemetry.start_iteration(iteration_id="it-1", iteration_index=1)
    agent_telemetry = iteration_telemetry.start_agent_execution(
        run_agent_id="ra-1",
        execution_index=1,
    )

    agent_telemetry.finish_failed(
        error=RuntimeError("Connection error."),
        tool_calls_count=0,
    )

    assert len(observer.agent_execution_finished) == 1
    finished = observer.agent_execution_finished[0]
    assert finished.status == "failed"
    assert finished.error_type == "RuntimeError"
    assert finished.error_message_short == "Connection error."


def test_run_telemetry_no_run_id_parameter() -> None:
    observer = FakeObserver()
    run_telemetry = RunTelemetry(observer=observer, run_id="run-123")

    run_telemetry.record_test_execution(
        phase="baseline",
        command=" pytest",
        exit_code=0,
        timed_out=False,
        signature="sig",
        iteration=0,
    )

    assert observer.test_records[0].run_id == "run-123"


def test_agent_execution_telemetry_forwards_provider_retry_event() -> None:
    observer = FakeObserver()
    run_telemetry = RunTelemetry(observer=observer, run_id="run-1")
    iteration_telemetry = run_telemetry.start_iteration(iteration_id="it-1", iteration_index=1)
    agent_telemetry = iteration_telemetry.start_agent_execution(
        run_agent_id="ra-1",
        execution_index=1,
    )

    agent_telemetry.handle_provider_call_event(
        ProviderCallEvent(
            event_type="retryable_failure",
            agent_execution_id=agent_telemetry.agent_execution_id,
            attempt=1,
            total_attempts=3,
            status_code=500,
            error_type="RuntimeError",
            error_message_short="boom",
            tool_calls_count=2,
        )
    )

    assert len(observer.provider_call_records) == 1
    record = observer.provider_call_records[0]
    assert record.event_type == "retryable_failure"
    assert record.attempt == 1
    assert record.total_attempts == 3
    assert record.status_code == 500

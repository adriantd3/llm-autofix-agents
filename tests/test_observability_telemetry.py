from llm_autofix_agents.observability.telemetry import RunTelemetry


class FakeObserver:
    def __init__(self) -> None:
        self.test_records = []

    def on_test_execution(self, *, record):
        self.test_records.append(record)


def test_run_telemetry_records_test_execution() -> None:
    observer = FakeObserver()
    telemetry = RunTelemetry(observer=observer)

    telemetry.record_test_execution(
        run_id="run-1",
        iteration=1,
        phase="iteration_validation",
        command="pytest",
        exit_code=0,
        timed_out=False,
        signature="abc123",
        iteration_id="it-1",
        agent_execution_id="agent-1",
    )

    assert len(observer.test_records) == 1
    assert observer.test_records[0].run_id == "run-1"
    assert observer.test_records[0].phase == "iteration_validation"

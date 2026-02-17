import json
import tempfile
from pathlib import Path

from darwincode.state.run_state import RunStateStore
from darwincode.types.models import (
    AgentResult,
    AgentStatus,
    AgentTask,
    EvalResult,
    GenerationRecord,
    Hypothesis,
    PlanStep,
    RunState,
    RunStatus,
)


def test_save_and_load_empty_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStateStore(Path(tmpdir))
        state = RunState(
            id="test-run",
            status=RunStatus.RUNNING,
            current_step=0,
            current_generation=0,
        )
        store.save(state)
        loaded = store.load("test-run")
        assert loaded is not None
        assert loaded.id == "test-run"
        assert loaded.status == RunStatus.RUNNING


def test_save_and_load_full_state():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStateStore(Path(tmpdir))

        state = RunState(
            id="full-run",
            status=RunStatus.COMPLETED,
            current_step=1,
            current_generation=2,
            plan_steps=[
                PlanStep(index=0, description="Step 1", prompt="Do step 1"),
                PlanStep(index=1, description="Step 2", prompt="Do step 2"),
            ],
            generations=[
                GenerationRecord(
                    generation=0,
                    step_index=0,
                    tasks=[
                        AgentTask(
                            id="a-001",
                            generation=0,
                            step_index=0,
                            prompt="Fix it",
                            repo_snapshot_path="/tmp/snap",
                        )
                    ],
                    results=[
                        AgentResult(
                            task_id="a-001",
                            status=AgentStatus.SUCCESS,
                            output="Done",
                            patch_path="/tmp/patch.diff",
                            duration_seconds=30.0,
                        )
                    ],
                    eval_results=[
                        EvalResult(
                            task_id="a-001",
                            passed=True,
                            score=1.0,
                            details="All tests passed",
                        )
                    ],
                    winner_id="a-001",
                    hypothesis=Hypothesis(
                        generation=0,
                        winner_id="a-001",
                        analysis="Good approach",
                        prompt_delta="Be more specific",
                    ),
                )
            ],
            hypotheses=[
                Hypothesis(
                    generation=0,
                    winner_id="a-001",
                    analysis="Good approach",
                    prompt_delta="Be more specific",
                )
            ],
        )

        store.save(state)
        loaded = store.load("full-run")

        assert loaded is not None
        assert loaded.status == RunStatus.COMPLETED
        assert len(loaded.plan_steps) == 2
        assert len(loaded.generations) == 1
        assert loaded.generations[0].winner_id == "a-001"
        assert loaded.generations[0].hypothesis is not None
        assert len(loaded.hypotheses) == 1


def test_list_runs():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStateStore(Path(tmpdir))

        for i in range(3):
            state = RunState(
                id=f"run-{i}",
                status=RunStatus.COMPLETED,
                current_step=0,
                current_generation=0,
            )
            store.save(state)

        runs = store.list_runs()
        assert len(runs) == 3


def test_load_nonexistent():
    with tempfile.TemporaryDirectory() as tmpdir:
        store = RunStateStore(Path(tmpdir))
        assert store.load("nonexistent") is None

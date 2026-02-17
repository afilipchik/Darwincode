from darwincode.types.config import DarwinConfig
from darwincode.types.models import (
    AgentResult,
    AgentStatus,
    AgentTask,
    EvalResult,
    EvalSpec,
    GenerationRecord,
    Hypothesis,
    PlanStep,
    RunState,
    RunStatus,
)


def test_agent_task_creation():
    task = AgentTask(
        id="test-001",
        generation=0,
        step_index=0,
        prompt="Fix the bug",
        repo_snapshot_path="/tmp/repo",
    )
    assert task.id == "test-001"
    assert task.generation == 0
    assert task.parent_hypotheses == []


def test_agent_result():
    result = AgentResult(
        task_id="test-001",
        status=AgentStatus.SUCCESS,
        output="Done",
        patch_path="/tmp/patch.diff",
        duration_seconds=42.5,
    )
    assert result.status == AgentStatus.SUCCESS
    assert result.duration_seconds == 42.5


def test_eval_spec_defaults():
    spec = EvalSpec(command="pytest tests/")
    assert spec.timeout == 120
    assert spec.success_criteria == "exit-code"
    assert spec.expected_output is None


def test_hypothesis():
    h = Hypothesis(
        generation=1,
        winner_id="agent-abc",
        analysis="Winner used better error handling",
        prompt_delta="Add error handling instructions",
    )
    assert h.generation == 1
    assert h.winner_id == "agent-abc"


def test_darwin_config():
    config = DarwinConfig(
        plan="Implement a REST API",
        eval=EvalSpec(command="pytest"),
        repo_path="/tmp/my-project",
    )
    assert config.population_size == 5
    assert config.max_generations == 3
    assert config.agent_vendor == "claude-code"
    assert config.timeout == 300


def test_darwin_config_custom():
    config = DarwinConfig(
        plan="Fix bug",
        eval=EvalSpec(command="npm test", timeout=60),
        repo_path="/tmp/project",
        population_size=10,
        max_generations=5,
        timeout=600,
    )
    assert config.population_size == 10
    assert config.max_generations == 5


def test_run_state():
    state = RunState(
        id="run-123",
        status=RunStatus.RUNNING,
        current_step=0,
        current_generation=0,
    )
    assert state.plan_steps == []
    assert state.generations == []
    assert state.hypotheses == []


def test_generation_record():
    record = GenerationRecord(
        generation=0,
        step_index=0,
        tasks=[],
        results=[],
        eval_results=[],
    )
    assert record.winner_id is None
    assert record.hypothesis is None

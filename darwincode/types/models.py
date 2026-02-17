from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    TIMEOUT = "timeout"
    ERROR = "error"


class RunStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Hypothesis:
    generation: int
    winner_id: str
    analysis: str
    prompt_delta: str


@dataclass
class PlanStep:
    index: int
    description: str
    prompt: str


@dataclass
class AgentTask:
    id: str
    generation: int
    step_index: int
    prompt: str
    repo_snapshot_path: str
    parent_hypotheses: list[Hypothesis] = field(default_factory=list)


@dataclass
class AgentResult:
    task_id: str
    status: AgentStatus
    output: str
    patch_path: str
    duration_seconds: float
    transcript_path: str | None = None


@dataclass
class EvalSpec:
    command: str
    timeout: int = 120
    success_criteria: str = "exit-code"
    expected_output: str | None = None
    protected_paths: list[str] = field(default_factory=list)


@dataclass
class EvalResult:
    task_id: str
    passed: bool
    score: float
    details: str


@dataclass
class GenerationRecord:
    generation: int
    step_index: int
    tasks: list[AgentTask]
    results: list[AgentResult]
    eval_results: list[EvalResult]
    winner_id: str | None = None
    hypothesis: Hypothesis | None = None


@dataclass
class TaskStatus:
    task_id: str
    status: AgentStatus
    elapsed_seconds: float
    progress: str = ""


@dataclass
class WorkflowStatus:
    generation: int
    step_index: int
    tasks: list[TaskStatus]


@dataclass
class RunState:
    id: str
    status: RunStatus
    current_step: int
    current_generation: int
    plan_steps: list[PlanStep] = field(default_factory=list)
    generations: list[GenerationRecord] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)

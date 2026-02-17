from __future__ import annotations

import json
import logging
from pathlib import Path

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

logger = logging.getLogger(__name__)


class RunStateStore:
    """Persist and load run state to/from disk as JSON."""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, run_id: str) -> Path:
        return self.base_dir / f"{run_id}.json"

    def save(self, state: RunState) -> None:
        data = _serialize_state(state)
        path = self._path(state.id)
        path.write_text(json.dumps(data, indent=2))

    def load(self, run_id: str) -> RunState | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        data = json.loads(path.read_text())
        return _deserialize_state(data)

    def list_runs(self) -> list[RunState]:
        runs = []
        for path in sorted(self.base_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                runs.append(_deserialize_state(data))
            except (json.JSONDecodeError, KeyError):
                logger.warning("Skipping corrupt state file: %s", path)
        return runs


def _serialize_state(state: RunState) -> dict:
    return {
        "id": state.id,
        "status": state.status.value,
        "current_step": state.current_step,
        "current_generation": state.current_generation,
        "plan_steps": [
            {"index": s.index, "description": s.description, "prompt": s.prompt}
            for s in state.plan_steps
        ],
        "generations": [_serialize_gen(g) for g in state.generations],
        "hypotheses": [_serialize_hypothesis(h) for h in state.hypotheses],
    }


def _serialize_gen(gen: GenerationRecord) -> dict:
    return {
        "generation": gen.generation,
        "step_index": gen.step_index,
        "tasks": [
            {
                "id": t.id,
                "generation": t.generation,
                "step_index": t.step_index,
                "prompt": t.prompt,
                "repo_snapshot_path": t.repo_snapshot_path,
            }
            for t in gen.tasks
        ],
        "results": [
            {
                "task_id": r.task_id,
                "status": r.status.value,
                "output": r.output[:1000],
                "patch_path": r.patch_path,
                "duration_seconds": r.duration_seconds,
            }
            for r in gen.results
        ],
        "eval_results": [
            {
                "task_id": e.task_id,
                "passed": e.passed,
                "score": e.score,
                "details": e.details[:1000],
            }
            for e in gen.eval_results
        ],
        "winner_id": gen.winner_id,
        "hypothesis": _serialize_hypothesis(gen.hypothesis) if gen.hypothesis else None,
    }


def _serialize_hypothesis(h: Hypothesis) -> dict:
    return {
        "generation": h.generation,
        "winner_id": h.winner_id,
        "analysis": h.analysis,
        "prompt_delta": h.prompt_delta,
    }


def _deserialize_state(data: dict) -> RunState:
    return RunState(
        id=data["id"],
        status=RunStatus(data["status"]),
        current_step=data["current_step"],
        current_generation=data["current_generation"],
        plan_steps=[
            PlanStep(index=s["index"], description=s["description"], prompt=s["prompt"])
            for s in data.get("plan_steps", [])
        ],
        generations=[_deserialize_gen(g) for g in data.get("generations", [])],
        hypotheses=[_deserialize_hypothesis(h) for h in data.get("hypotheses", [])],
    )


def _deserialize_gen(data: dict) -> GenerationRecord:
    return GenerationRecord(
        generation=data["generation"],
        step_index=data["step_index"],
        tasks=[
            AgentTask(
                id=t["id"],
                generation=t["generation"],
                step_index=t["step_index"],
                prompt=t["prompt"],
                repo_snapshot_path=t.get("repo_snapshot_path", ""),
            )
            for t in data.get("tasks", [])
        ],
        results=[
            AgentResult(
                task_id=r["task_id"],
                status=AgentStatus(r["status"]),
                output=r["output"],
                patch_path=r["patch_path"],
                duration_seconds=r["duration_seconds"],
            )
            for r in data.get("results", [])
        ],
        eval_results=[
            EvalResult(
                task_id=e["task_id"],
                passed=e["passed"],
                score=e["score"],
                details=e["details"],
            )
            for e in data.get("eval_results", [])
        ],
        winner_id=data.get("winner_id"),
        hypothesis=_deserialize_hypothesis(data["hypothesis"])
        if data.get("hypothesis")
        else None,
    )


def _deserialize_hypothesis(data: dict) -> Hypothesis:
    return Hypothesis(
        generation=data["generation"],
        winner_id=data["winner_id"],
        analysis=data["analysis"],
        prompt_delta=data["prompt_delta"],
    )

from __future__ import annotations

import asyncio
import logging
import os
import shutil
from pathlib import Path

from darwincode.k8s.volumes import WORKSPACES_BASE
from darwincode.types.models import AgentResult, AgentStatus, EvalResult, EvalSpec

logger = logging.getLogger(__name__)


class EvalRunner:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id

    async def evaluate(self, result: AgentResult, eval_spec: EvalSpec) -> EvalResult:
        """Run the eval command against an agent's modified repo."""
        if result.status not in (AgentStatus.SUCCESS, AgentStatus.FAILURE):
            logger.warning(
                "Skipping eval for %s: status=%s", result.task_id, result.status.value
            )
            return EvalResult(
                task_id=result.task_id,
                passed=False,
                score=0.0,
                details=f"Agent status: {result.status.value}, skipping eval",
            )

        workspace = WORKSPACES_BASE / self.run_id / result.task_id
        repo_dir = workspace / "repo"

        if not repo_dir.exists():
            return EvalResult(
                task_id=result.task_id,
                passed=False,
                score=0.0,
                details="Repo directory not found",
            )

        # If protected paths exist, eval against a merged copy:
        # agent's code + pristine validation harness
        eval_dir = self._prepare_eval_dir(workspace, repo_dir)

        try:
            # Build a PATH that includes the project .venv (if it exists) so
            # eval commands like "python -m pytest" find the right interpreter
            # and test tools.
            env = os.environ.copy()
            venv_bin = Path(__file__).resolve().parents[2] / ".venv" / "bin"
            if venv_bin.is_dir():
                env["PATH"] = str(venv_bin) + os.pathsep + env.get("PATH", "")
            elif shutil.which("pytest") is None:
                logger.warning("pytest not found on PATH — eval may fail")

            proc = await asyncio.create_subprocess_shell(
                eval_spec.command,
                cwd=str(eval_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=eval_spec.timeout
            )
            output = stdout.decode() + "\n" + stderr.decode()
            exit_code = proc.returncode or 0

        except asyncio.TimeoutError:
            return EvalResult(
                task_id=result.task_id,
                passed=False,
                score=0.0,
                details=f"Eval timed out after {eval_spec.timeout}s",
            )
        except Exception as e:
            return EvalResult(
                task_id=result.task_id,
                passed=False,
                score=0.0,
                details=f"Eval error: {e}",
            )

        if eval_spec.success_criteria == "exit-code":
            passed = exit_code == 0
            score = 1.0 if passed else _parse_test_score(output)
        elif eval_spec.success_criteria == "output-match":
            expected = eval_spec.expected_output or ""
            passed = expected in output
            score = 1.0 if passed else 0.0
        else:
            passed = exit_code == 0
            score = 1.0 if passed else 0.0

        # Clean up temporary eval dir if we created one
        if eval_dir != repo_dir and eval_dir.exists():
            shutil.rmtree(eval_dir)

        logger.info(
            "Eval %s: exit=%d passed=%s score=%.3f cmd=%s",
            result.task_id, exit_code, passed, score, eval_spec.command,
        )

        return EvalResult(
            task_id=result.task_id,
            passed=passed,
            score=score,
            details=output[-2000:],  # Keep last 2000 chars
        )

    @staticmethod
    def _prepare_eval_dir(workspace: Path, repo_dir: Path) -> Path:
        """Create eval directory: agent's code + pristine validation harness.

        If no pristine/ snapshot exists (no --protect flags), returns repo_dir
        directly (backward compatible). Otherwise, copies repo/ to eval/ and
        overlays pristine protected files so the eval harness is tamper-proof.
        """
        pristine_dir = workspace / "pristine"
        if not pristine_dir.exists():
            return repo_dir

        eval_dir = workspace / "eval"
        if eval_dir.exists():
            shutil.rmtree(eval_dir)
        shutil.copytree(repo_dir, eval_dir, symlinks=True)

        # Overlay pristine protected files (the validation harness)
        for item in pristine_dir.rglob("*"):
            if item.is_file():
                rel = item.relative_to(pristine_dir)
                dest = eval_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)

        logger.info("Prepared eval dir with protected harness at %s", eval_dir)
        return eval_dir


def _parse_test_score(output: str) -> float:
    """Try to extract a partial score from test output (e.g. '8 passed, 2 failed')."""
    import re

    # pytest summary line: counts may appear in any order
    passed_match = re.search(r"(\d+) passed", output)
    failed_match = re.search(r"(\d+) failed", output)
    error_match = re.search(r"(\d+) error", output)

    passed = int(passed_match.group(1)) if passed_match else 0
    failed = int(failed_match.group(1)) if failed_match else 0
    errors = int(error_match.group(1)) if error_match else 0

    total = passed + failed + errors
    if total > 0:
        return passed / total

    return 0.0

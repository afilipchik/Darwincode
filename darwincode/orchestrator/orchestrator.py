from __future__ import annotations

import logging
import shutil
import uuid
from pathlib import Path

from rich.console import Console

from darwincode.agents.registry import get_vendor
from darwincode.cli.display import Display
from darwincode.k8s.infra import InfraManager
from darwincode.k8s.volumes import WORKSPACES_BASE
from darwincode.orchestrator.analyzer import Analyzer
from darwincode.orchestrator.evolution import EvolutionEngine
from darwincode.orchestrator.planner import Planner
from darwincode.state.run_state import RunStateStore
from darwincode.types.config import DarwinConfig
from darwincode.types.models import (
    GenerationRecord,
    RunState,
    RunStatus,
)
from darwincode.workflow.local_engine import LocalWorkflowEngine

logger = logging.getLogger(__name__)
console = Console()

DEFAULT_STATE_DIR = Path.home() / ".darwincode" / "runs"


class Orchestrator:
    """Main evolution loop orchestrator."""

    def __init__(self, config: DarwinConfig) -> None:
        self.config = config
        self.run_id = uuid.uuid4().hex[:12]
        self.vendor = get_vendor(config.agent_vendor)
        self.planner = Planner()
        self.analyzer = Analyzer()
        self.evolution = EvolutionEngine(self.vendor)
        self.infra = InfraManager(
            cluster_mode=config.cluster_mode,
            cluster_name=config.cluster_name,
            console=console,
        )
        self.engine = LocalWorkflowEngine(
            run_id=self.run_id,
            repo_path=config.repo_path,
            cluster_name=config.cluster_name,
            protected_paths=config.eval.protected_paths,
        )
        self.state_store = RunStateStore(DEFAULT_STATE_DIR)
        self.display = Display(console)
        self.state = RunState(
            id=self.run_id,
            status=RunStatus.PENDING,
            current_step=0,
            current_generation=0,
        )

    async def run(self) -> RunState:
        """Execute the full evolution loop."""
        self.state.status = RunStatus.RUNNING
        self.state_store.save(self.state)
        self.display.show_header(self.run_id)

        try:
            # Step 0: Ensure infrastructure is ready (auto-init Kind in local mode)
            self.display.show_status("Checking infrastructure...")
            self.infra.ensure_ready()

            # Step 1: Decompose plan into steps
            self.display.show_status("Decomposing plan...")
            steps = self.planner.decompose(self.config.plan)
            self.state.plan_steps = steps
            self.state_store.save(self.state)
            self.display.show_plan(steps)

            # Step 2: Execute each step with evolution
            for step in steps:
                self.state.current_step = step.index
                self.state_store.save(self.state)
                self.display.show_step_start(step)

                winner_id = await self._evolve_step(step.index, step.prompt)

                if winner_id:
                    # Apply the winning patch
                    self._apply_winner(winner_id)
                    self.display.show_winner(winner_id, step.index)
                else:
                    self.display.show_no_winner(step.index)

            self.state.status = RunStatus.COMPLETED
            self.state_store.save(self.state)
            self.display.show_completed(self.state)

        except KeyboardInterrupt:
            self.display.show_status("Cancelled by user. Cleaning up...")
            await self.engine.cancel()
            self.state.status = RunStatus.CANCELLED
            self.state_store.save(self.state)

        except Exception as e:
            logger.exception("Evolution run failed")
            self.state.status = RunStatus.FAILED
            self.state_store.save(self.state)
            self.display.show_error(str(e))

        return self.state

    async def _evolve_step(self, step_index: int, base_prompt: str) -> str | None:
        """Run the evolution loop for a single step. Returns winner task_id or None."""
        hypotheses = []

        for gen in range(self.config.max_generations):
            self.state.current_generation = gen
            self.state_store.save(self.state)

            # Create population
            if gen == 0:
                tasks = self.evolution.create_initial_population(
                    base_prompt, step_index, self.config.population_size
                )
            else:
                tasks = self.evolution.evolve(
                    base_prompt, step_index, gen,
                    self.config.population_size, hypotheses
                )

            self.display.show_generation_start(step_index, gen, len(tasks))

            # Execute generation
            results = await self.engine.execute_generation(tasks, self.config.timeout)

            # Run eval
            eval_results = await self.engine.run_eval(results, self.config.eval)

            # Record generation
            winner_id = self.analyzer.pick_winner(results, eval_results)

            record = GenerationRecord(
                generation=gen,
                step_index=step_index,
                tasks=tasks,
                results=results,
                eval_results=eval_results,
                winner_id=winner_id,
            )

            # Display results
            self.display.show_generation_results(record)

            # Check if we have a passing winner
            best_eval = max(eval_results, key=lambda e: e.score) if eval_results else None
            if best_eval and best_eval.passed:
                record.winner_id = best_eval.task_id
                self.state.generations.append(record)
                self.state_store.save(self.state)
                return best_eval.task_id

            # Analyze and create hypothesis for next generation
            if gen < self.config.max_generations - 1:
                hypothesis = self.analyzer.analyze(
                    base_prompt, results, eval_results, gen
                )
                record.hypothesis = hypothesis
                hypotheses.append(hypothesis)
                self.state.hypotheses.append(hypothesis)
                self.display.show_hypothesis(hypothesis)

            self.state.generations.append(record)
            self.state_store.save(self.state)

        # No generation produced a passing result — return the best we got
        return winner_id

    def _apply_winner(self, winner_id: str) -> None:
        """Apply the winning agent's changes to the repo."""
        workspace = WORKSPACES_BASE / self.run_id / winner_id
        patch_file = workspace / "results" / "patch.diff"

        if patch_file.exists() and patch_file.stat().st_size > 0:
            # Copy the modified repo files over the original
            winner_repo = workspace / "repo"
            if winner_repo.exists():
                # Apply by copying the entire repo state
                dest = Path(self.config.repo_path)
                # Only copy non-.git files
                for item in winner_repo.iterdir():
                    if item.name == ".git":
                        continue
                    dest_item = dest / item.name
                    if item.is_dir():
                        if dest_item.exists():
                            shutil.rmtree(dest_item)
                        shutil.copytree(item, dest_item)
                    else:
                        shutil.copy2(item, dest_item)
                logger.info("Applied winner '%s' changes to repo", winner_id)

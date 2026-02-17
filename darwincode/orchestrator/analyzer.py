from __future__ import annotations

import json
import logging

from darwincode.orchestrator.llm import claude_query
from darwincode.types.models import AgentResult, EvalResult, Hypothesis

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """\
You are analyzing the results of multiple AI coding agents that attempted the same task.
Each agent took a different approach. Analyze why the top performers did better.

Task prompt: {prompt}

Results (sorted by eval score, best first):
{results_text}

Based on this analysis:
1. Explain WHY the winning approach was better (be specific about code strategies, not vague).
2. Identify what the losers did wrong or differently.
3. Suggest what prompt modifications could help future agents perform better.

Respond in JSON format:
{{
    "analysis": "Why the winner succeeded (2-3 sentences)",
    "prompt_delta": "Specific prompt additions/modifications for next generation"
}}
"""


class Analyzer:
    def analyze(
        self,
        prompt: str,
        results: list[AgentResult],
        eval_results: list[EvalResult],
        generation: int,
    ) -> Hypothesis:
        """Analyze results and produce a hypothesis about why the winner was better."""
        # Sort by score descending
        paired = list(zip(results, eval_results))
        paired.sort(key=lambda x: x[1].score, reverse=True)

        results_text = ""
        for result, eval_result in paired:
            results_text += f"\n--- Agent {result.task_id} (score: {eval_result.score:.2f}) ---\n"
            results_text += f"Status: {result.status.value}\n"
            results_text += f"Eval passed: {eval_result.passed}\n"
            results_text += f"Output excerpt: {result.output[:500]}\n"
            results_text += f"Eval details: {eval_result.details[:500]}\n"

        text = claude_query(
            ANALYSIS_PROMPT.format(prompt=prompt, results_text=results_text)
        )

        if text.strip().startswith("```"):
            lines = text.strip().split("\n")
            text = "\n".join(lines[1:-1])

        data = json.loads(text)
        winner_id = paired[0][0].task_id if paired else ""

        return Hypothesis(
            generation=generation,
            winner_id=winner_id,
            analysis=data.get("analysis", ""),
            prompt_delta=data.get("prompt_delta", ""),
        )

    def pick_winner(
        self, results: list[AgentResult], eval_results: list[EvalResult]
    ) -> str | None:
        """Pick the best agent by eval score. Returns task_id or None."""
        if not eval_results:
            return None

        best = max(zip(results, eval_results), key=lambda x: x[1].score)
        if best[1].score > 0:
            return best[0].task_id
        return None

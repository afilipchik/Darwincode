from __future__ import annotations

from darwincode.agents.vendor import AgentVendor
from darwincode.types.models import AgentTask, Hypothesis

PROMPT_STRATEGIES = [
    "",  # Default: no extra framing
    "Think step by step. Break the problem down before writing code.",
    "Focus on writing minimal, correct code. Prioritize passing tests over completeness.",
    "Start by reading existing code carefully. Match the project's patterns and conventions.",
    "Consider edge cases. Write defensive code that handles unexpected inputs.",
]


class ClaudeCodeVendor(AgentVendor):
    @property
    def name(self) -> str:
        return "claude-code"

    def build_task_config(self, task: AgentTask) -> dict:
        return {
            "id": task.id,
            "generation": task.generation,
            "vendor": self.name,
            "prompt": task.prompt,
            "parent_hypotheses": [
                {"analysis": h.analysis, "prompt_delta": h.prompt_delta}
                for h in task.parent_hypotheses
            ],
        }

    def build_prompt(
        self,
        base_prompt: str,
        hypotheses: list[Hypothesis],
        variant_index: int,
    ) -> str:
        parts = [base_prompt]

        # Add a strategy variant for diversity
        strategy = PROMPT_STRATEGIES[variant_index % len(PROMPT_STRATEGIES)]
        if strategy:
            parts.append(f"\nApproach: {strategy}")

        # Incorporate learnings from previous generations
        if hypotheses:
            parts.append("\n--- Learnings from previous attempts ---")
            for h in hypotheses:
                parts.append(f"- {h.analysis}")
            parts.append("Use these insights to improve your approach.")

        return "\n".join(parts)

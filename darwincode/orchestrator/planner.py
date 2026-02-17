from __future__ import annotations

import json
import logging
import re

from darwincode.orchestrator.llm import claude_query
from darwincode.types.models import PlanStep

logger = logging.getLogger(__name__)

DECOMPOSE_PROMPT = """\
You are a software engineering planner. Given a high-level coding task, decompose it into \
ordered implementation steps. Each step should be independently implementable and testable.

Output a JSON array of steps. Each step has:
- "index": step number (0-based)
- "description": short description of what this step accomplishes
- "prompt": detailed prompt that a coding agent should receive to implement this step

Be specific in the prompt — include file paths, function signatures, and expected behavior where possible.

IMPORTANT: Respond ONLY with the raw JSON array. No markdown, no explanation, no code fences.

Task:
{plan}
"""


def _extract_json_array(text: str) -> list:
    """Extract a JSON array from text that may contain surrounding prose."""
    text = text.strip()

    # Strip markdown code fences
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        text = "\n".join(lines[1:])
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]

    # Try parsing as-is
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Find the first [ ... ] block
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"Could not extract JSON array from response: {text[:200]}")


class Planner:
    def decompose(self, plan: str) -> list[PlanStep]:
        """Use AI to decompose a high-level plan into ordered steps."""
        text = claude_query(DECOMPOSE_PROMPT.format(plan=plan))
        logger.debug("Planner raw response: %s", text[:500])

        steps_data = _extract_json_array(text)

        steps = []
        for s in steps_data:
            steps.append(
                PlanStep(
                    index=s["index"],
                    description=s["description"],
                    prompt=s["prompt"],
                )
            )

        logger.info("Decomposed plan into %d steps", len(steps))
        return steps

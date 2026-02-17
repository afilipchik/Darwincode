from darwincode.agents.claude_code import ClaudeCodeVendor
from darwincode.agents.registry import get_vendor
from darwincode.orchestrator.evolution import EvolutionEngine
from darwincode.types.models import Hypothesis


def test_get_vendor():
    vendor = get_vendor("claude-code")
    assert vendor.name == "claude-code"


def test_get_vendor_unknown():
    import pytest

    with pytest.raises(ValueError, match="Unknown agent vendor"):
        get_vendor("nonexistent")


def test_claude_code_build_prompt_no_hypotheses():
    vendor = ClaudeCodeVendor()
    prompt = vendor.build_prompt("Fix the add function", [], 0)
    assert "Fix the add function" in prompt


def test_claude_code_build_prompt_with_strategy():
    vendor = ClaudeCodeVendor()
    prompt = vendor.build_prompt("Fix the add function", [], 1)
    assert "Fix the add function" in prompt
    assert "step by step" in prompt.lower()


def test_claude_code_build_prompt_with_hypotheses():
    vendor = ClaudeCodeVendor()
    hypotheses = [
        Hypothesis(
            generation=0,
            winner_id="agent-001",
            analysis="Winner handled edge cases better",
            prompt_delta="Add edge case handling",
        )
    ]
    prompt = vendor.build_prompt("Fix the add function", hypotheses, 0)
    assert "edge cases" in prompt.lower()
    assert "Learnings" in prompt


def test_evolution_create_initial_population():
    vendor = ClaudeCodeVendor()
    engine = EvolutionEngine(vendor)
    tasks = engine.create_initial_population("Fix the bug", step_index=0, population_size=3)
    assert len(tasks) == 3
    assert all(t.generation == 0 for t in tasks)
    assert all(t.step_index == 0 for t in tasks)
    # Each task should have a unique ID
    ids = [t.id for t in tasks]
    assert len(set(ids)) == 3


def test_evolution_evolve():
    vendor = ClaudeCodeVendor()
    engine = EvolutionEngine(vendor)
    hypotheses = [
        Hypothesis(
            generation=0,
            winner_id="agent-001",
            analysis="Tests passed because of better validation",
            prompt_delta="Include input validation",
        )
    ]
    tasks = engine.evolve("Fix the bug", step_index=0, generation=1, population_size=2, hypotheses=hypotheses)
    assert len(tasks) == 2
    assert all(t.generation == 1 for t in tasks)
    assert all(len(t.parent_hypotheses) == 1 for t in tasks)

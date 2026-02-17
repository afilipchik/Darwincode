# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Darwincode applies evolutionary principles to AI code generation. It spawns N parallel AI coding agents in isolated Kubernetes containers, evaluates their results against a test harness, picks winners, records hypotheses about why they won, and uses that analysis to create the next generation of prompts.

## Build & Run

```bash
# Setup (use uv, not pip)
uv venv --python 3.12 .venv
source .venv/bin/activate
uv pip install -e "."

# Run tests
pytest tests/ -v

# Run a single test
pytest tests/test_types.py::test_agent_task_creation -v

# Lint
ruff check darwincode/

# CLI
darwincode --help
darwincode init          # Create Kind cluster + build agent image
darwincode run --plan "task" --eval "pytest" --repo ./project
darwincode status        # Check running experiment
darwincode logs <agent-id>
darwincode results
darwincode destroy       # Tear down Kind cluster
```

## Architecture

The system follows a layered architecture:

- **CLI** (`darwincode/cli/`) — click-based commands with rich TUI display
- **Orchestrator** (`darwincode/orchestrator/`) — main evolution loop, plan decomposition (AI-powered), result analysis, prompt mutation
- **Workflow Engine** (`darwincode/workflow/`) — abstract `WorkflowEngine` ABC decouples orchestration from execution. `LocalWorkflowEngine` uses asyncio + K8s Jobs. Designed for future Temporal swap
- **Agents** (`darwincode/agents/`) — `AgentVendor` ABC for agent vendors. `ClaudeCodeVendor` is the first implementation. Add new vendors by implementing the ABC and registering in `registry.py`
- **K8s** (`darwincode/k8s/`) — Kind cluster management, Job creation/monitoring, shared volume setup
- **Eval** (`darwincode/eval/`) — runs user-provided test commands against each agent's modified repo, parses scores
- **Transcript** (`darwincode/transcript/`) — two-layer capture: raw JSONL (Claude Code stream-json) + post-processed structured transcript with typed segments (THOUGHT, CODE_WRITE, CODE_EDIT, COMMAND, etc.)
- **State** (`darwincode/state/`) — JSON-based run state persistence at `~/.darwincode/runs/`

## Key Patterns

- Agent workspaces are mounted at `/tmp/darwincode-workspaces/<run-id>/<agent-id>/` on host, `/workspace/` in pods
- Each workspace contains: `task.json`, `repo/`, `results/`, `transcript/`
- The `WorkflowEngine` ABC is the main extension point for changing execution backends
- `AgentVendor` ABC is the extension point for adding new AI agent providers
- Prompt diversity is achieved through strategy variants in `ClaudeCodeVendor.build_prompt()`
- Anthropic API is used for plan decomposition and result analysis (via `anthropic` SDK)

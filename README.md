# Darwincode

Apply evolution to code development. Spawn parallel AI coding agents, evaluate their output against a test harness, pick winners, record hypotheses about why they won, and use that analysis to create the next generation of prompts.

## How it works

1. You provide a **plan** (high-level goal) and an **eval** (test command)
2. Darwincode decomposes the plan into ordered steps using AI
3. For each step, it spawns **N agents** in isolated Kubernetes pods (Kind)
4. Each agent independently attempts the task with a different prompt strategy
5. Results are evaluated against your test harness and scored
6. A **winner** is selected and their changes are applied
7. If no agent passes, Darwincode **analyzes why** top performers did better, records a hypothesis, mutates the prompts, and spawns the next generation
8. This loop repeats until the tests pass or max generations are reached

```text
Plan --> Decompose --> [Agent A, Agent B, Agent C, ...] --> Eval --> Pick Winner
                              |                                        |
                              +--- next gen (mutated prompts) <--------+
                                   informed by hypotheses
```

## Prerequisites

- Python 3.12+
- Docker
- [Kind](https://kind.sigs.k8s.io/) (`brew install kind`)
- [uv](https://docs.astral.sh/uv/) (`brew install uv`)
- [Claude Code](https://claude.ai/code) CLI installed and logged in (`claude` command available)

## Quick start

```bash
# Setup
make setup

# Build agent Docker image and create Kind cluster
make init

# Run an evolution experiment
source .venv/bin/activate
darwincode run \
  --plan "Implement a function that sorts a list" \
  --eval "pytest tests/" \
  --repo ./my-project \
  --population 5 \
  --generations 3
```

## Makefile targets

```text
make setup         Create venv and install dependencies
make test          Run tests
make lint          Run linter
make build-image   Build the agent Docker image
make init          Build image + create Kind cluster + load image
make destroy       Tear down the Kind cluster
make clean         Remove build artifacts
```

## CLI commands

```text
darwincode init       Initialize Kind cluster and build agent images
darwincode run        Run an evolution experiment (interactive)
darwincode status     Check status of running experiments
darwincode logs       Tail logs for a specific agent
darwincode results    View results and hypotheses
darwincode destroy    Tear down the Kind cluster
```

## Architecture

```text
CLI (darwincode)
  |
  v
Workflow Engine (abstract ABC -- swappable for Temporal)
  |
  +-- Orchestrator (plan decomposition, evolution loop, analysis)
  +-- Agent Vendors (Claude Code CLI, extensible to Codex, etc.)
  +-- K8s/Kind Manager (cluster, jobs, volumes, pod monitoring)
  +-- Eval Harness (run tests, score results)
  +-- Transcript Capture (raw JSONL + structured segments)
```

Each agent runs in an isolated Kind pod with a pre-built Docker image containing Python, Node.js, Go, Rust, Claude Code CLI, and common dev tools. Communication between the orchestrator and agents happens via a shared filesystem (hostPath volumes).

## Agent transcript capture

Every agent's full conversation is captured in two layers:

- **Raw**: Claude Code's `stream-json` output saved as JSONL (lossless, replayable)
- **Structured**: Post-processed into typed segments (`THOUGHT`, `CODE_WRITE`, `CODE_EDIT`, `COMMAND`, etc.) for easy filtering and analysis

## Adding a new agent vendor

Implement the `AgentVendor` ABC in `darwincode/agents/` and register it in `darwincode/agents/registry.py`. The vendor needs to provide:

- `build_task_config()` -- generate the task.json for the container
- `build_prompt()` -- create prompt variants with hypothesis-informed mutations

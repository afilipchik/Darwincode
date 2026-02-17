#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="/workspace"
TASK_FILE="${WORKSPACE}/task.json"
RESULTS_DIR="${WORKSPACE}/results"
TRANSCRIPT_DIR="${WORKSPACE}/transcript"
REPO_DIR="${WORKSPACE}/repo"

mkdir -p "${RESULTS_DIR}" "${TRANSCRIPT_DIR}"

# Write running status
write_status() {
    local status="$1"
    local progress="${2:-}"
    jq -n --arg s "$status" --arg p "$progress" \
        '{"status": $s, "progress": $p, "timestamp": now | todate}' \
        > "${RESULTS_DIR}/status.json"
}

# Read task
if [ ! -f "${TASK_FILE}" ]; then
    echo "ERROR: task.json not found at ${TASK_FILE}" >&2
    write_status "error" "task.json not found"
    exit 1
fi

VENDOR=$(jq -r '.vendor // "claude-code"' "${TASK_FILE}")
PROMPT=$(jq -r '.prompt' "${TASK_FILE}")
AGENT_CONFIG=$(jq -r '.agent_config // "{}"' "${TASK_FILE}")

write_status "running" "Starting agent: ${VENDOR}"

cd "${REPO_DIR}"

# Trust workspace repo (files created by host user, running as root in container)
git config --global --add safe.directory "${REPO_DIR}"

# Initialize git if needed (for diff tracking)
if [ ! -d .git ]; then
    git init
    git add -A
    git commit -m "Initial state" --allow-empty
fi

INITIAL_SHA=$(git rev-parse HEAD)

# Dispatch to the right agent vendor
run_agent() {
    case "${VENDOR}" in
        claude-code)
            # Run Claude Code in headless mode with stream-json output
            claude --dangerously-skip-permissions \
                -p "${PROMPT}" \
                --output-format stream-json \
                --verbose \
                2>"${RESULTS_DIR}/stderr.log" \
                | tee "${TRANSCRIPT_DIR}/raw.jsonl" \
                | jq -r 'select(.type == "assistant") | .message.content[]? | select(.type == "text") | .text // empty' \
                > "${RESULTS_DIR}/output.log" || true
            ;;
        codex)
            # Future: Codex CLI integration
            echo "ERROR: codex vendor not yet implemented" >&2
            write_status "error" "codex vendor not implemented"
            exit 1
            ;;
        *)
            echo "ERROR: Unknown vendor '${VENDOR}'" >&2
            write_status "error" "Unknown vendor: ${VENDOR}"
            exit 1
            ;;
    esac
}

# Run the agent, capture exit code
AGENT_EXIT=0
run_agent || AGENT_EXIT=$?

# Generate diff of all changes
git add -A
git diff --cached "${INITIAL_SHA}" > "${RESULTS_DIR}/patch.diff" 2>/dev/null || true

# Write final status
if [ "${AGENT_EXIT}" -eq 0 ]; then
    write_status "done" "Agent completed successfully"
else
    write_status "error" "Agent exited with code ${AGENT_EXIT}"
fi

exit ${AGENT_EXIT}

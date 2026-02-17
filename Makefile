CLUSTER_NAME ?= darwincode
IMAGE_NAME ?= darwincode-agent
IMAGE_TAG ?= latest

.PHONY: help setup install test lint build-image init destroy clean

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: ## Create venv and install dependencies (for development)
	uv venv --python 3.12 .venv
	. .venv/bin/activate && uv pip install -e "." && uv pip install pytest pytest-asyncio ruff

install: ## Install darwincode globally (available from anywhere)
	uv tool install --python 3.12 -e .

uninstall: ## Uninstall global darwincode
	uv tool uninstall darwincode

test: ## Run tests
	. .venv/bin/activate && python -m pytest tests/ -v

lint: ## Run linter
	. .venv/bin/activate && ruff check darwincode/

build-image: ## Build the agent Docker image
	docker build -t $(IMAGE_NAME):$(IMAGE_TAG) docker/agent/

load-image: ## Load agent image into Kind cluster
	kind load docker-image $(IMAGE_NAME):$(IMAGE_TAG) --name $(CLUSTER_NAME)

init: build-image ## Create Kind cluster and load agent image
	@kind get clusters 2>/dev/null | grep -q $(CLUSTER_NAME) \
		&& echo "Cluster '$(CLUSTER_NAME)' already exists" \
		|| . .venv/bin/activate && python -c "from darwincode.k8s.cluster import ClusterManager; ClusterManager('$(CLUSTER_NAME)').create()"
	kind load docker-image $(IMAGE_NAME):$(IMAGE_TAG) --name $(CLUSTER_NAME)
	@echo "\033[32mDarwincode initialized.\033[0m"

destroy: ## Tear down the Kind cluster
	kind delete cluster --name $(CLUSTER_NAME)

clean: ## Remove build artifacts
	rm -rf .venv/ dist/ build/ *.egg-info .pytest_cache .ruff_cache __pycache__
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

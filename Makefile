# Common tasks. Each target is a thin wrapper around a uv command.

# On macOS, iCloud Drive marks dot-folders such as .venv as hidden, and Python
# 3.12 skips hidden .pth files, which breaks the project's editable install.
# So when the project sits in a synced Documents folder, the environment lives
# outside it. In that case, use these targets (`make install`, not `uv sync`).
ifneq (,$(findstring /Documents/,$(CURDIR)))
export UV_PROJECT_ENVIRONMENT := $(HOME)/.venvs/trustlayer
endif

.PHONY: install fmt lint test eval site check clean

install:  ## Create the environment and install the project plus dev tools
	uv sync

fmt:  ## Format the code and apply safe lint fixes
	uv run ruff format .
	uv run ruff check --fix .

lint:  ## Check formatting and lint rules without changing files
	uv run ruff format --check .
	uv run ruff check .

test:  ## Run the test suite
	uv run pytest

eval:  ## Run every scenario and write results/results.json
	uv run trustlayer eval --scenarios scenarios --out results/results.json

site:  ## Build the static results page into _site/
	uv run trustlayer site --results results/results.json --out _site

check: lint test eval site  ## Everything CI runs, in the same order

clean:  ## Delete generated files and tool caches
	rm -rf results _site .pytest_cache .ruff_cache .hypothesis

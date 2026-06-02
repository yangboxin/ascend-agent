# Ascend Agent — development shortcuts
#
# Quick start:
#   make install    ←  one-time: install Python + Node.js deps
#   asd             ←  launch the full-screen TUI
#   make tui        ←  same as `asd`
#   make server     ←  start the legacy SSE chat server
#   make react-tui  ←  launch the legacy Ink+React TUI
#
# After make install (editable mode), Python code changes are live immediately.
# Node.js code is only needed for the legacy React TUI.

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install python-install node-install tui server react-tui dev test clean help

# ---- One-time setup ----

install: python-install node-install
	@echo ""
	@echo "✓  All deps installed."
	@echo "   Launch:      asd"
	@echo "   Or:          make tui"

python-install: $(VENV)
	$(PIP) install -e ".[dev]"
	@echo "✓  Python deps (editable mode)"

node-install:
	cd cli && npm install
	@echo "✓  Node.js deps"

$(VENV):
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip setuptools

# ---- Running ----

tui:
	@test -f $(PYTHON) || { echo "Run 'make install' first."; exit 1; }
	$(PYTHON) -m ascend_agent

server:
	@test -f $(PYTHON) || { echo "Run 'make install' first."; exit 1; }
	$(PYTHON) -m ascend_agent.cli.tui_server

react-tui:
	@cd cli && npx tsx src/index.tsx --server http://127.0.0.1:9020

dev:
	@echo "Starting legacy server + React TUI (requires tmux)..."
	@tmux new-session -d -s asd "$(PYTHON) -m ascend_agent.cli.tui_server" \; \
		split-window -h "cd cli && npx tsx src/index.tsx --server http://127.0.0.1:9020" \; \
		attach-session -t asd

repl:
	@test -f $(PYTHON) || { echo "Run 'make install' first."; exit 1; }
	$(PYTHON) -m ascend_agent --repl

# ---- Testing ----

test:
	@test -f $(PYTHON) || { echo "Run 'make python-install' first."; exit 1; }
	$(PYTHON) -m pytest tests/ -x -q --tb=short 2>&1 | tail -20

test-all:
	@test -f $(PYTHON) || { echo "Run 'make python-install' first."; exit 1; }
	$(PYTHON) -m pytest tests/ -q --tb=short

# ---- Cleanup ----

clean:
	rm -rf $(VENV) src/*.egg-info .pytest_cache **/__pycache__ cli/node_modules
	@echo "Cleaned.  Run 'make install' to rebuild."

help:
	@echo "make install         one-time: Python + Node.js deps"
	@echo "asd                  launch the full-screen TUI"
	@echo "make tui             launch the full-screen TUI"
	@echo "make server          start legacy SSE chat server"
	@echo "make react-tui       launch legacy Ink+React TUI"
	@echo "make dev             start legacy server+React TUI in tmux"
	@echo "make repl            simple Python REPL"
	@echo "make test            run tests"
	@echo "make clean           remove venv & node_modules"

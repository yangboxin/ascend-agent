# Ascend Agent — development shortcuts
#
# Quick start:
#   make install    ←  one-time: install Python + Node.js deps
#   make tui        ←  launch the Ink+React TUI
#   make server     ←  start the SSE chat server (in one terminal)
#   make dev        ←  start server + TUI together (tmux)
#
# After make install (editable mode), Python code changes are live immediately.
# Node.js code runs via tsx, no build step needed.

VENV := .venv
PYTHON := $(VENV)/bin/python
PIP := $(VENV)/bin/pip

.PHONY: install python-install node-install tui server dev test clean help

# ---- One-time setup ----

install: python-install node-install
	@echo ""
	@echo "✓  All deps installed."
	@echo "   Terminal 1:  make server"
	@echo "   Terminal 2:  make tui"
	@echo "   Or both:     make dev"

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
	@cd cli && npx tsx src/index.tsx

server:
	@test -f $(PYTHON) || { echo "Run 'make install' first."; exit 1; }
	$(PYTHON) -m ascend_agent.cli.tui_server

dev:
	@echo "Starting server + TUI (requires tmux)..."
	@tmux new-session -d -s asd "$(PYTHON) -m ascend_agent.cli.tui_server" \; \
		split-window -h "cd cli && npx tsx src/index.tsx --server http://127.0.0.1:9020" \; \
		attach-session -t asd

repl:
	@test -f $(VENV)/bin/asd || { echo "Run 'make install' first."; exit 1; }
	$(VENV)/bin/asd --repl

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
	@echo "make tui             launch the Ink+React TUI"
	@echo "make server          start SSE chat server"
	@echo "make dev             start server+TUI in tmux"
	@echo "make repl            simple Python REPL"
	@echo "make test            run tests"
	@echo "make clean           remove venv & node_modules"

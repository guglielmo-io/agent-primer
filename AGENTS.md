# Agent Instructions

## Project Context

Agent Primer is a local-first GUI that prepares repositories for AI coding agents. It creates and verifies context files; it is not a coding agent and must not modify target application code.

## Before Editing

- Read `README.md` for product positioning.
- Read tests before changing scanner, scoring, prompt, writer, or API behavior.
- Use `rg` for search.
- Keep changes small and evidence-driven.

## Commands

- Run Python tests with `pytest -q`.
- Check frontend JavaScript with `node --check web/app.js`.
- Run the app with `agent-primer` after installing with `pip install -e ".[dev]"`.

## Constraints

- Do not hardcode secrets or API keys.
- Do not add cloud storage or telemetry.
- Do not add product-code editing behavior.
- Keep generated context compact; future coding agents pay for every token.
- Keep the GUI dark-theme only.

## Done When

- Relevant tests pass.
- README and user-facing labels match behavior.
- Security impact is stated for config, path, or API changes.

# Contributing

Agent Primer is intentionally small. Contributions should make AI coding agents more reliable without turning the tool into a coding agent.

## Development Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
```

Run the app:

```bash
agent-primer
```

## Contribution Rules

- Keep context files compact and evidence-driven.
- Do not add target-project code modification features.
- Do not store secrets in generated files, logs, screenshots, or tests.
- Prefer deterministic repository scans over LLM guesses.
- Add tests for scoring, prompt, writer, scanner, and API behavior changes.
- Keep the GUI minimal and dark-theme only unless the project direction changes.

## Pull Request Checklist

- `pytest -q` passes.
- `node --check web/app.js` passes.
- New generated files are covered by `.gitignore` where appropriate.
- README changes reflect user-visible behavior.
- Security-sensitive changes explain how secrets and target paths are handled.

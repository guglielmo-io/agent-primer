# Changelog

All notable changes to Agent Primer will be documented in this file.

## Unreleased

- Rebuilt Prompt Upgrade on researched LLM/coding-agent prompting best practices: weighted intent routing, a coding-optimized template (bias to action, anti-patterns, `rg`/`path:line`, narrow-to-broad verification), and an upgraded AI rewrite prompt.
- Surfaced OpenRouter failures instead of silently falling back: when a key is configured but the AI call fails, the prompt-upgrade and repair flows return a clear warning.
- Added deterministic dependency extraction from manifests (Python, Node, Go, Rust) into the context docs to reduce `AGENT_FILL` guesswork.
- Added language-agnostic entry-point detection and broadened symbolic areas (routes, models/migrations, background jobs, auth) beyond the JavaScript ecosystem.
- Hardened scanning against malformed manifests.
- Fixed New Project failing with an unreadable "[object Object]" error: validation errors now render as readable text, and project names with spaces are normalized (e.g. `My Project` -> `My-Project`).
- Added a `ruff` + `mypy --strict` quality gate and CI checks.

## 0.1.0 - 2026-05-22

- Added local FastAPI GUI for creating repository context packs.
- Added new-project, existing-repo setup, and verification/repair modes.
- Added AGENTS.md and docs/ai template generation.
- Added repo-map and symbolic-area detection.
- Added context-readiness scoring and repair prompts.
- Added OpenRouter settings with persistent local config.
- Added custom OpenRouter model IDs alongside the curated model presets.
- Added Linux desktop launcher and custom icon.

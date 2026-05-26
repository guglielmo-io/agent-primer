from pathlib import Path

from conftest import FIXTURES
from agent_primer.context_pack import build_context_pack, build_existing_template_pack
from agent_primer.models import AiContextDraft, RepoScan
from agent_primer.scoring import score_context_pack, score_existing_context


def test_complete_pack_scores_ready():
    draft = AiContextDraft.example(project_name="Example")
    scan = RepoScan(
        root_path="/repo",
        root_files=["README.md", "package.json"],
        top_level_dirs=["src", "tests"],
        commands={"test": "pnpm test", "build": "pnpm build"},
        ci_files=[".github/workflows/ci.yml"],
    )
    pack = build_context_pack(scan, draft)

    score = score_context_pack(pack, scan)

    assert score.total >= 85
    assert score.ready is True


def test_bad_context_is_capped_and_has_findings():
    score = score_existing_context(FIXTURES / "bad_context")

    assert score.total < 85
    assert score.ready is False
    assert any(finding.code == "generic_marker" for finding in score.findings)


def test_missing_symbolic_repo_map_gets_actionable_finding():
    scan = RepoScan(
        root_path="/repo",
        root_files=["package.json"],
        top_level_dirs=["src"],
        commands={"test": "pnpm test"},
        symbolic_areas=[
            {"name": "Auth Boundary", "paths": ["src/middleware.ts"], "evidence": ["src/middleware.ts"]},
        ],
    )
    pack = build_context_pack(scan, AiContextDraft.example(project_name="Example"))
    pack.files["docs/ai/repo-map.md"] = "# Repo Map\n\n- src\n"

    score = score_context_pack(pack, scan)

    assert any(finding.code == "missing_symbolic_area" for finding in score.findings)


def test_uncompiled_template_markers_block_readiness():
    scan = RepoScan(
        root_path="/repo",
        root_files=["README.md", "package.json"],
        top_level_dirs=["src"],
        commands={"lint": "npm run lint", "build": "npm run build"},
    )
    pack = build_existing_template_pack(scan)

    score = score_context_pack(pack, scan)

    assert score.ready is False
    assert score.total < 85
    assert any(finding.code == "uncompiled_template" for finding in score.findings)


def test_stale_npm_script_commands_are_reported():
    scan = RepoScan(
        root_path="/repo",
        root_files=["package.json"],
        top_level_dirs=["src"],
        commands={"lint": "npm run lint", "build": "npm run build"},
        package_manager="npm",
    )
    pack = build_context_pack(scan, AiContextDraft.example(project_name="Example"))
    pack.files["docs/ai/verification.md"] = """# Verification

## Detected Commands
- lint: `npm lint`
- build: `npm build`
"""

    score = score_context_pack(pack, scan)

    assert score.ready is False
    assert any(finding.code == "stale_verification_command" for finding in score.findings)


def test_scoring_accepts_executable_command_variants_and_ignores_dev_scripts():
    scan = RepoScan(
        root_path="/repo",
        root_files=["README.md"],
        top_level_dirs=["bot", "mcp-servers", "tests"],
        commands={
            "bot:test": "PYTHONPATH=bot python -m unittest discover -s tests",
            "mcp-servers/posthog:install": "npm --prefix mcp-servers/posthog install",
            "mcp-servers/posthog:build": "npm --prefix mcp-servers/posthog run build",
            "mcp-servers/posthog:dev": "npm --prefix mcp-servers/posthog run dev",
        },
        symbolic_areas=[
            {"name": "Test Surface", "paths": ["tests/test_config.py"], "evidence": ["tests/test_config.py"]},
        ],
    )
    pack = build_context_pack(scan, AiContextDraft.example(project_name="Example"))
    pack.files["docs/ai/verification.md"] = """# Verification

## Detected Commands
- Python unit suite: `PYTHONPATH=bot .venv/bin/python -m unittest discover -s tests`
- PostHog MCP install: `npm --prefix mcp-servers/posthog install`
- PostHog MCP build: `npm --prefix mcp-servers/posthog run build`

## Verification Ladder
- Run focused checks first.

## Evidence
- Commands verified from nested manifests.
"""

    score = score_context_pack(pack, scan)

    assert score.ready is True
    assert score.total >= 85
    assert not score.findings

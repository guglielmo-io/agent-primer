from pathlib import Path

from conftest import FIXTURES
from agent_primer.context_pack import build_context_pack
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

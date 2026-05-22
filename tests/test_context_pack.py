from agent_primer.context_pack import build_context_pack, build_existing_template_pack
from agent_primer.models import AiContextDraft, RepoScan


def test_context_pack_generates_required_files():
    draft = AiContextDraft.example(project_name="Example")
    scan = RepoScan(root_path="/repo", top_level_dirs=["src"], root_files=["README.md"])

    pack = build_context_pack(scan, draft)

    assert set(pack.files) == {
        "AGENTS.md",
        "docs/ai/product.md",
        "docs/ai/context.md",
        "docs/ai/architecture.md",
        "docs/ai/verification.md",
        "docs/ai/constraints.md",
        "docs/ai/risks.md",
        "docs/ai/repo-map.md",
    }


def test_context_pack_avoids_forbidden_markers():
    draft = AiContextDraft.example(project_name="Example")
    scan = RepoScan(root_path="/repo", top_level_dirs=["src"], root_files=["README.md"])

    pack = build_context_pack(scan, draft)
    joined = "\n".join(pack.files.values())

    assert "TODO" not in joined
    assert "TBD" not in joined
    assert "Lorem ipsum" not in joined
    assert "Fill this in" not in joined


def test_existing_template_pack_contains_agent_fill_contract():
    scan = RepoScan(
        root_path="/repo",
        top_level_dirs=["src"],
        root_files=["README.md"],
        manifest_files=["package.json"],
        commands={"test": "npm test"},
    )

    pack = build_existing_template_pack(scan)
    joined = "\n".join(pack.files.values())

    assert set(pack.files) == set(build_context_pack(scan, AiContextDraft.example()).files)
    assert "AGENT_FILL" in joined
    assert "npm test" in pack.files["docs/ai/verification.md"]
    assert "Do not guess" in joined

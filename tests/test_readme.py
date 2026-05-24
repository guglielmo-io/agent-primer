from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_readme_documents_agent_file_aliases_and_global_rule():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "CLAUDE.md" in readme
    assert "GEMINI.md" in readme
    assert "rename or copy" in readme
    assert "Global instruction" in readme
    assert "docs/ai/*.md" in readme

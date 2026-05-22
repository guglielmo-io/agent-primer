from pathlib import Path

from conftest import FIXTURES
from agent_primer.context_pack import build_context_pack, build_existing_template_pack
from agent_primer.models import AiContextDraft
from agent_primer.prompt_compiler import compile_existing_fill_prompt, compile_new_project_validation_prompt
from agent_primer.scanner import scan_repo
from agent_primer.scoring import score_existing_context
from agent_primer.writer import write_context_pack


def test_existing_repo_setup_flow_writes_templates_and_fill_prompt(tmp_path: Path):
    target = tmp_path / "repo"
    _copy_fixture(FIXTURES / "node_repo", target)
    scan = scan_repo(target)
    pack = build_existing_template_pack(scan)

    write_result = write_context_pack(target, pack)
    prompt = compile_existing_fill_prompt(str(target), pack)

    assert "AGENTS.md" in write_result.updated_files
    assert "AGENT_FILL" in (target / "docs/ai/context.md").read_text(encoding="utf-8")
    assert str(target) in prompt
    assert "Do not modify application code" in prompt


def test_new_project_flow_writes_context_pack(tmp_path: Path):
    target = tmp_path / "new-project"
    target.mkdir()
    scan = scan_repo(target)
    draft = AiContextDraft.example(project_name="New Project")
    pack = build_context_pack(scan, draft)

    write_context_pack(target, pack)
    prompt = compile_new_project_validation_prompt(str(target), pack)

    assert (target / "AGENTS.md").exists()
    assert (target / "docs/ai/product.md").exists()
    assert "Do not blindly accept" in prompt


def test_repair_flow_detects_bad_context():
    score = score_existing_context(FIXTURES / "bad_context")

    assert score.ready is False
    assert score.total < 85


def _copy_fixture(source: Path, target: Path) -> None:
    for path in source.rglob("*"):
        if path.is_dir():
            continue
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

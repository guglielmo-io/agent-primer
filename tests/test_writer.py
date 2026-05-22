from pathlib import Path

from agent_primer.models import ContextPack
from agent_primer.writer import plan_writes, write_context_pack


def test_writer_preserves_existing_files_by_default(tmp_path: Path):
    target = tmp_path / "repo"
    target.mkdir()
    (target / "AGENTS.md").write_text("human", encoding="utf-8")
    pack = ContextPack(files={"AGENTS.md": "agent"})

    result = write_context_pack(target, pack, overwrite=False)

    assert (target / "AGENTS.md").read_text(encoding="utf-8") == "human"
    assert result.actions[0].action == "keep"


def test_writer_backs_up_before_overwrite(tmp_path: Path):
    target = tmp_path / "repo"
    target.mkdir()
    (target / "AGENTS.md").write_text("human", encoding="utf-8")
    pack = ContextPack(files={"AGENTS.md": "agent"})

    result = write_context_pack(target, pack, overwrite=True)

    assert (target / "AGENTS.md").read_text(encoding="utf-8") == "agent"
    assert result.backup_path is not None
    assert (Path(result.backup_path) / "AGENTS.md").exists()


def test_plan_writes_never_exposes_api_key(tmp_path: Path):
    pack = ContextPack(files={"docs/ai/context.md": "safe"})

    planned = plan_writes(tmp_path, pack, api_key="secret-key")

    assert "secret-key" not in str(planned)

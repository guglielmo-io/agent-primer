from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path

from agent_primer.models import ContextPack, WriteAction, WriteResult


def plan_writes(target: Path, pack: ContextPack, api_key: str | None = None, overwrite: bool = False) -> list[WriteAction]:
    actions: list[WriteAction] = []
    for relative_path in sorted(pack.files):
        path = target / relative_path
        if path.exists() and not overwrite:
            action = "keep"
        elif path.exists():
            action = "update"
        else:
            action = "create"
        actions.append(WriteAction(action=action, path=relative_path))
    return actions


def write_context_pack(target: Path, pack: ContextPack, overwrite: bool = False) -> WriteResult:
    actions = plan_writes(target, pack, overwrite=overwrite)
    backup_path = _backup_path(target) if overwrite and _has_existing(target, pack) else None
    updated_files: list[str] = []

    for action in actions:
        destination = target / action.path
        if action.action == "keep":
            continue
        if destination.exists() and backup_path:
            _backup_file(target, destination, backup_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(pack.files[action.path], encoding="utf-8")
        updated_files.append(action.path)

    return WriteResult(actions=actions, backup_path=str(backup_path) if backup_path else None, updated_files=updated_files)


def _backup_path(target: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = target / ".agent-primer" / "backups" / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def _has_existing(target: Path, pack: ContextPack) -> bool:
    return any((target / relative_path).exists() for relative_path in pack.files)


def _backup_file(root: Path, source: Path, backup_root: Path) -> None:
    relative_path = source.relative_to(root)
    destination = backup_root / relative_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)

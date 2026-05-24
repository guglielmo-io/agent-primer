from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent_primer.config import AppConfig, ConfigStore
from agent_primer.context_pack import build_context_pack, build_existing_template_pack
from agent_primer.model_presets import model_presets, model_request_options
from agent_primer.models import AiContextDraft, ContextPack, RepoScan, SetupMode, SetupRequest
from agent_primer.openrouter import OpenRouterClient
from agent_primer.prompt_compiler import (
    compile_existing_fill_prompt,
    compile_new_project_validation_prompt,
    compile_repair_prompt,
)
from agent_primer.prompts import new_project_planner_prompt
from agent_primer.scanner import scan_repo
from agent_primer.scoring import score_existing_context
from agent_primer.writer import plan_writes, write_context_pack


class ScanRequest(BaseModel):
    target_path: Path


class ConfigRequest(BaseModel):
    openrouter_api_key: str | None = None
    last_model: str | None = None


class PickDirectoryRequest(BaseModel):
    initial_path: str | None = None


def create_app(config_store: ConfigStore | None = None) -> FastAPI:
    app = FastAPI(title="Agent Primer")
    store = config_store or ConfigStore()
    web_dir = Path(__file__).resolve().parents[2] / "web"
    if web_dir.exists():
        app.mount("/static", StaticFiles(directory=web_dir), name="static")

    @app.middleware("http")
    async def no_cache_static_assets(request, call_next):
        response = await call_next(request)
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(web_dir / "index.html")

    @app.get("/api/health")
    def health() -> dict[str, object]:
        return {"ok": True, "app": "agent-primer"}

    @app.get("/api/fs/home")
    def fs_home() -> dict[str, str]:
        return {"path": str(Path.home())}

    @app.get("/api/fs/list")
    def fs_list(path: str | None = Query(default=None)) -> dict[str, object]:
        current = _resolve_directory(path)
        directories = []
        for child in current.iterdir():
            try:
                if not child.is_dir():
                    continue
                directories.append({
                    "name": child.name,
                    "path": str(child.resolve()),
                    "hidden": child.name.startswith("."),
                })
            except OSError:
                continue
        directories.sort(key=lambda item: (item["hidden"], str(item["name"]).lower()))
        parent = None if current.parent == current else str(current.parent)
        return {"path": str(current), "parent": parent, "directories": directories}

    @app.post("/api/fs/pick-directory")
    def pick_directory(request: PickDirectoryRequest) -> dict[str, str | None]:
        selected = _run_directory_picker(request.initial_path)
        return {"path": str(selected) if selected else None}

    @app.get("/api/config/openrouter")
    def read_openrouter_config() -> dict[str, object]:
        config = store.load()
        return {
            "api_key_configured": bool(store.get_api_key()),
            "last_model": config.last_model,
        }

    @app.get("/api/models")
    async def models() -> dict[str, object]:
        key = store.get_api_key()
        if not key:
            raise HTTPException(status_code=400, detail="OpenRouter API key is missing")
        return {"models": [model.model_dump() for model in await OpenRouterClient(key).list_models()]}

    @app.get("/api/model-presets")
    def read_model_presets() -> dict[str, object]:
        return {"models": model_presets()}

    @app.post("/api/config/openrouter")
    def save_openrouter_config(request: ConfigRequest) -> dict[str, bool]:
        current = store.load()
        store.save(AppConfig(
            openrouter_api_key=request.openrouter_api_key or current.openrouter_api_key,
            last_model=request.last_model or current.last_model,
            recent_paths=current.recent_paths,
        ))
        return {"ok": True}

    @app.post("/api/scan")
    def scan(request: ScanRequest) -> dict[str, object]:
        if not request.target_path.exists():
            raise HTTPException(status_code=404, detail="Target path not found")
        return {"scan": scan_repo(request.target_path).model_dump()}

    @app.post("/api/setup/dry-run")
    async def dry_run(request: SetupRequest) -> dict[str, object]:
        target, _, pack, next_prompt, message = await _build_setup_pack(request, store)
        planned = plan_writes(target, pack, overwrite=_effective_overwrite(request))
        return {
            "mode": request.mode.value,
            "message": message,
            "planned_writes": [action.model_dump() for action in planned],
            "next_prompt": next_prompt,
        }

    @app.post("/api/setup/apply")
    async def apply_setup(request: SetupRequest) -> dict[str, object]:
        target, _, pack, next_prompt, message = await _build_setup_pack(request, store)
        write_result = write_context_pack(target, pack, overwrite=_effective_overwrite(request))
        return {
            "mode": request.mode.value,
            "message": message,
            "updated_files": write_result.updated_files,
            "backup_path": write_result.backup_path,
            "next_prompt": next_prompt,
        }

    @app.post("/api/verify")
    def verify(request: ScanRequest) -> dict[str, object]:
        score = score_existing_context(request.target_path)
        return {
            "mode": SetupMode.VERIFY_REPAIR.value,
            "message": "Context verification completed.",
            "score": score.model_dump(),
            "repair_prompt": compile_repair_prompt(str(request.target_path), score) if not score.ready else None,
        }

    return app


def _resolve_directory(path: str | None) -> Path:
    candidate = Path(path).expanduser() if path else Path.home()
    try:
        resolved = candidate.resolve()
    except OSError as exc:
        raise HTTPException(status_code=400, detail="Path cannot be resolved") from exc
    if not resolved.exists() or not resolved.is_dir():
        raise HTTPException(status_code=400, detail="Path is not a directory")
    return resolved


async def _build_setup_pack(request: SetupRequest, store: ConfigStore) -> tuple[Path, RepoScan, ContextPack, str, str]:
    if request.mode == SetupMode.VERIFY_REPAIR:
        raise HTTPException(status_code=400, detail="Use /api/verify for context verification")
    target = _target_path(request)
    target.mkdir(parents=True, exist_ok=True)
    scan_result = scan_repo(target)
    if request.mode == SetupMode.NEW_PROJECT:
        draft = await _draft_new_project_context(request, scan_result, store)
        pack = build_context_pack(scan_result, draft)
        prompt = compile_new_project_validation_prompt(str(target), pack)
        return target, scan_result, pack, prompt, "Provisional project context created."
    pack = build_existing_template_pack(scan_result)
    prompt = compile_existing_fill_prompt(str(target), pack)
    return target, scan_result, pack, prompt, "Context templates created."


def _target_path(request: SetupRequest) -> Path:
    if request.mode == SetupMode.NEW_PROJECT:
        return request.target_path / str(request.project_name)
    return request.target_path


def _effective_overwrite(request: SetupRequest) -> bool:
    return request.mode == SetupMode.NEW_PROJECT and request.overwrite


async def _draft_new_project_context(request: SetupRequest, scan_result: RepoScan, store: ConfigStore) -> AiContextDraft:
    key = store.get_api_key(request.openrouter_api_key)
    if not key:
        return AiContextDraft.example(project_name=request.project_name or Path(scan_result.root_path).name)
    client = OpenRouterClient(key)
    prompt = new_project_planner_prompt(str(request.project_name), str(request.raw_idea))
    data = await client.complete_json(request.openrouter_model, prompt, **model_request_options(request.openrouter_model))
    return AiContextDraft(project_name=request.project_name or Path(scan_result.root_path).name, **data)


def _run_directory_picker(initial_path: str | None) -> Path | None:
    initial = _resolve_initial_path(initial_path)
    command = _directory_picker_command(initial)
    if command is None:
        raise HTTPException(status_code=500, detail="No native directory picker found for this operating system.")
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except OSError as exc:
        raise HTTPException(status_code=500, detail="Could not open directory picker") from exc
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        detail = result.stderr.strip() or "Directory picker failed"
        raise HTTPException(status_code=500, detail=detail)
    selected = Path(result.stdout.strip()).expanduser()
    if not selected.exists() or not selected.is_dir():
        raise HTTPException(status_code=400, detail="Selected path is not a directory")
    return selected.resolve()


def _resolve_initial_path(initial_path: str | None) -> Path:
    if not initial_path:
        return Path.home()
    candidate = Path(initial_path).expanduser()
    if candidate.is_file():
        return candidate.parent.resolve()
    if candidate.exists():
        return candidate.resolve()
    return Path.home()


def _directory_picker_command(initial: Path) -> list[str] | None:
    if sys.platform == "darwin":
        return _macos_directory_picker_command(initial)
    if sys.platform.startswith("win"):
        return _windows_directory_picker_command(initial)
    return _linux_directory_picker_command(initial)


def _linux_directory_picker_command(initial: Path) -> list[str] | None:
    if shutil.which("zenity"):
        return [
            "zenity",
            "--file-selection",
            "--directory",
            "--title=Choose repository folder for Agent Primer",
            "--width=900",
            "--height=650",
            f"--filename={initial}/",
        ]
    if shutil.which("kdialog"):
        return ["kdialog", "--getexistingdirectory", str(initial)]
    if shutil.which("yad"):
        return ["yad", "--file", "--directory", "--title=Choose folder", f"--filename={initial}/"]
    return None


def _macos_directory_picker_command(initial: Path) -> list[str] | None:
    if not shutil.which("osascript"):
        return None
    initial_path = str(initial).replace('"', '\\"')
    script = (
        'POSIX path of (choose folder with prompt "Choose repository folder for Agent Primer" '
        f'default location POSIX file "{initial_path}/")'
    )
    return ["osascript", "-e", script]


def _windows_directory_picker_command(initial: Path) -> list[str] | None:
    command = shutil.which("powershell") or shutil.which("pwsh")
    if not command:
        return None
    initial_path = str(initial).replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$dialog = New-Object System.Windows.Forms.FolderBrowserDialog; "
        '$dialog.Description = "Choose repository folder for Agent Primer"; '
        f"$dialog.SelectedPath = '{initial_path}'; "
        "if ($dialog.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK) "
        "{ [Console]::Out.WriteLine($dialog.SelectedPath) } else { exit 1 }"
    )
    return [command, "-NoProfile", "-Command", script]

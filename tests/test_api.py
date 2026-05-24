from pathlib import Path

from conftest import FIXTURES
from fastapi.testclient import TestClient

from agent_primer.app import _directory_picker_command, create_app
from agent_primer.config import AppConfig, ConfigStore


def test_health_endpoint_returns_app_status():
    client = TestClient(create_app())

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "app": "agent-primer"}


def test_filesystem_picker_lists_directories_only(tmp_path):
    client = TestClient(create_app())
    (tmp_path / "repo").mkdir()
    (tmp_path / "file.txt").write_text("not a directory", encoding="utf-8")

    response = client.get("/api/fs/list", params={"path": str(tmp_path)})

    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == str(tmp_path)
    assert payload["parent"] == str(tmp_path.parent)
    assert payload["directories"] == [{"name": "repo", "path": str(tmp_path / "repo"), "hidden": False}]


def test_filesystem_picker_rejects_files(tmp_path):
    client = TestClient(create_app())
    file_path = tmp_path / "file.txt"
    file_path.write_text("not a directory", encoding="utf-8")

    response = client.get("/api/fs/list", params={"path": str(file_path)})

    assert response.status_code == 400


def test_openrouter_settings_report_persisted_state_without_secret(tmp_path):
    store = ConfigStore(tmp_path / "config.json")
    store.save(AppConfig(openrouter_api_key="secret", last_model="google/gemini-3.5-flash"))
    client = TestClient(create_app(config_store=store))

    response = client.get("/api/config/openrouter")

    assert response.status_code == 200
    assert response.json() == {
        "api_key_configured": True,
        "last_model": "google/gemini-3.5-flash",
    }


def test_model_presets_include_valid_default_and_premium_options():
    client = TestClient(create_app())

    response = client.get("/api/model-presets")

    payload = response.json()
    models = payload["models"]
    model_ids = [model["id"] for model in models]
    assert response.status_code == 200
    assert len(models) == 3
    assert model_ids[0] == "google/gemini-3.5-flash"
    assert [model["name"] for model in models] == [
        "Gemini 3.5 Flash",
        "GPT-5.5 Extra High",
        "Claude Opus 4.7 Max",
    ]


def test_native_directory_picker_returns_selected_path(tmp_path, monkeypatch):
    client = TestClient(create_app())
    monkeypatch.setattr("agent_primer.app._run_directory_picker", lambda initial_path: tmp_path)

    response = client.post("/api/fs/pick-directory", json={"initial_path": str(tmp_path.parent)})

    assert response.status_code == 200
    assert response.json() == {"path": str(tmp_path)}


def test_native_directory_picker_allows_cancel(monkeypatch):
    client = TestClient(create_app())
    monkeypatch.setattr("agent_primer.app._run_directory_picker", lambda initial_path: None)

    response = client.post("/api/fs/pick-directory", json={})

    assert response.status_code == 200
    assert response.json() == {"path": None}


def test_directory_picker_supports_linux_zenity(tmp_path, monkeypatch):
    monkeypatch.setattr("agent_primer.app.sys.platform", "linux")
    monkeypatch.setattr("agent_primer.app.shutil.which", lambda name: "/usr/bin/zenity" if name == "zenity" else None)

    command = _directory_picker_command(tmp_path)

    assert command[:3] == ["zenity", "--file-selection", "--directory"]


def test_directory_picker_supports_macos_osascript(tmp_path, monkeypatch):
    monkeypatch.setattr("agent_primer.app.sys.platform", "darwin")
    monkeypatch.setattr("agent_primer.app.shutil.which", lambda name: "/usr/bin/osascript" if name == "osascript" else None)

    command = _directory_picker_command(tmp_path)

    assert command[:2] == ["osascript", "-e"]
    assert "choose folder" in command[2]


def test_directory_picker_supports_windows_powershell(tmp_path, monkeypatch):
    monkeypatch.setattr("agent_primer.app.sys.platform", "win32")
    monkeypatch.setattr("agent_primer.app.shutil.which", lambda name: "powershell" if name == "powershell" else None)

    command = _directory_picker_command(tmp_path)

    assert command[:2] == ["powershell", "-NoProfile"]
    assert "FolderBrowserDialog" in command[3]


def test_existing_setup_is_template_only_and_does_not_call_ai(tmp_path, monkeypatch):
    target = tmp_path / "repo"
    _copy_fixture(FIXTURES / "node_repo", target)
    store = ConfigStore(tmp_path / "config.json")
    store.save(AppConfig(openrouter_api_key="secret", last_model="google/gemini-3.5-flash"))
    client = TestClient(create_app(config_store=store))

    async def fail_if_called(*args, **kwargs):
        raise AssertionError("existing setup must not call OpenRouter")

    monkeypatch.setattr("agent_primer.openrouter.OpenRouterClient.complete_json", fail_if_called)

    response = client.post("/api/setup/apply", json={
        "mode": "existing_project",
        "target_path": str(target),
        "openrouter_model": "google/gemini-3.5-flash",
        "overwrite": False,
    })

    payload = response.json()
    assert response.status_code == 200
    assert payload["mode"] == "existing_project"
    assert "score" not in payload
    assert "next_prompt" in payload
    assert "AGENT_FILL" in (target / "docs/ai/context.md").read_text(encoding="utf-8")


def test_existing_setup_ignores_overwrite_flag(tmp_path):
    target = tmp_path / "repo"
    _copy_fixture(FIXTURES / "node_repo", target)
    (target / "AGENTS.md").write_text("human-authored context", encoding="utf-8")
    client = TestClient(create_app(config_store=ConfigStore(tmp_path / "config.json")))

    response = client.post("/api/setup/apply", json={
        "mode": "existing_project",
        "target_path": str(target),
        "openrouter_model": "google/gemini-3.5-flash",
        "overwrite": True,
    })

    payload = response.json()
    assert response.status_code == 200
    assert payload["backup_path"] is None
    assert (target / "AGENTS.md").read_text(encoding="utf-8") == "human-authored context"


def test_new_project_setup_returns_validation_prompt_without_score(tmp_path):
    client = TestClient(create_app(config_store=ConfigStore(tmp_path / "config.json")))

    response = client.post("/api/setup/apply", json={
        "mode": "new_project",
        "target_path": str(tmp_path),
        "project_name": "new_app",
        "raw_idea": "A focused developer tool.",
        "openrouter_model": "google/gemini-3.5-flash",
        "overwrite": False,
    })

    payload = response.json()
    assert response.status_code == 200
    assert payload["mode"] == "new_project"
    assert "score" not in payload
    assert "Do not blindly accept" in payload["next_prompt"]


def test_verify_returns_score_and_repair_prompt():
    client = TestClient(create_app())

    response = client.post("/api/verify", json={"target_path": str(FIXTURES / "bad_context")})

    payload = response.json()
    assert response.status_code == 200
    assert payload["mode"] == "verify_repair"
    assert payload["score"]["ready"] is False
    assert payload["repair_prompt"]


def test_verify_returns_repair_prompt_for_uncompiled_template_context(tmp_path):
    target = tmp_path / "repo"
    _copy_fixture(FIXTURES / "node_repo", target)
    client = TestClient(create_app(config_store=ConfigStore(tmp_path / "config.json")))

    setup_response = client.post("/api/setup/apply", json={
        "mode": "existing_project",
        "target_path": str(target),
        "openrouter_model": "google/gemini-3.5-flash",
        "overwrite": False,
    })
    assert setup_response.status_code == 200

    response = client.post("/api/verify", json={"target_path": str(target)})

    payload = response.json()
    assert response.status_code == 200
    assert payload["score"]["ready"] is False
    assert any(finding["code"] == "uncompiled_template" for finding in payload["score"]["findings"])
    assert "AGENT_FILL" in payload["repair_prompt"]


def _copy_fixture(source: Path, target: Path) -> None:
    for path in source.rglob("*"):
        if path.is_dir():
            continue
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")

from pathlib import Path

from conftest import FIXTURES
from agent_primer.scanner import scan_repo


def test_node_repo_detects_package_scripts():
    scan = scan_repo(FIXTURES / "node_repo")

    assert scan.package_manager == "pnpm"
    assert scan.commands["test"] == "pnpm test"
    assert scan.commands["typecheck"] == "pnpm typecheck"
    assert ".github/workflows/ci.yml" in scan.ci_files
    assert "src/middleware.ts" in scan.critical_files


def test_node_repo_detects_symbolic_functional_areas():
    scan = scan_repo(FIXTURES / "node_repo")

    areas = {area.name: area.paths for area in scan.symbolic_areas}
    assert "Auth Boundary" in areas
    assert "API Routes" in areas
    assert "Database Layer" in areas
    assert "src/middleware.ts" in areas["Auth Boundary"]
    assert "src/app/api/auth/route.ts" in areas["API Routes"]
    assert "prisma/schema.prisma" in areas["Database Layer"]


def test_python_repo_detects_pytest_and_tools():
    scan = scan_repo(FIXTURES / "python_repo")

    assert scan.language_hints == ["Python"]
    assert scan.commands["test"] == "pytest"
    assert scan.commands["lint"] == "ruff check ."
    assert scan.commands["typecheck"] == "mypy ."
    assert ".env.example" in scan.env_examples


def test_empty_project_does_not_invent_commands(tmp_path: Path):
    scan = scan_repo(tmp_path)

    assert scan.commands == {}
    assert scan.manifest_files == []


def test_npm_non_lifecycle_scripts_use_run(tmp_path: Path):
    (tmp_path / "package.json").write_text(
        '{"scripts":{"dev":"vite","lint":"eslint .","build":"vite build","test":"vitest run"}}',
        encoding="utf-8",
    )

    scan = scan_repo(tmp_path)

    assert scan.commands["dev"] == "npm run dev"
    assert scan.commands["lint"] == "npm run lint"
    assert scan.commands["build"] == "npm run build"
    assert scan.commands["test"] == "npm test"


def test_scan_includes_top_level_nested_package_manifests(tmp_path: Path):
    (tmp_path / "package.json").write_text('{"scripts":{"build":"vite build"}}', encoding="utf-8")
    api_dir = tmp_path / "api"
    api_dir.mkdir()
    (api_dir / "package.json").write_text('{"scripts":{"dev":"nodemon src/index.js","start":"node src/index.js"}}', encoding="utf-8")

    scan = scan_repo(tmp_path)

    assert "package.json" in scan.manifest_files
    assert "api/package.json" in scan.manifest_files
    assert scan.commands["build"] == "npm run build"
    assert scan.commands["api:dev"] == "npm --prefix api run dev"
    assert scan.commands["api:start"] == "npm --prefix api start"


def test_scan_detects_deep_package_and_nested_python_project(tmp_path: Path):
    bot_dir = tmp_path / "bot"
    bot_dir.mkdir()
    (bot_dir / "requirements.txt").write_text("aiogram>=3\n", encoding="utf-8")
    (bot_dir / "main.py").write_text("print('ok')\n", encoding="utf-8")
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_config.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    cache_dir = tests_dir / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "test_config.cpython-312.pyc").write_bytes(b"cache")
    mcp_dir = tmp_path / "mcp-servers" / "posthog"
    mcp_dir.mkdir(parents=True)
    (mcp_dir / "package.json").write_text(
        '{"scripts":{"build":"tsc","dev":"tsx src/index.ts"}}',
        encoding="utf-8",
    )

    scan = scan_repo(tmp_path)
    areas = {area.name: area.paths for area in scan.symbolic_areas}

    assert "bot/requirements.txt" in scan.manifest_files
    assert "mcp-servers/posthog/package.json" in scan.manifest_files
    assert scan.source_dirs == ["bot"]
    assert scan.commands["bot:test"] == "PYTHONPATH=bot python -m unittest discover -s tests"
    assert scan.commands["mcp-servers/posthog:build"] == "npm --prefix mcp-servers/posthog run build"
    assert scan.commands["mcp-servers/posthog:dev"] == "npm --prefix mcp-servers/posthog run dev"
    assert "tests/test_config.py" in areas["Test Surface"]
    assert all("__pycache__" not in path for path in areas["Test Surface"])


def test_scan_ignores_generated_top_level_directories(tmp_path: Path):
    for name in ("src", "node_modules", "dist", "dist-server", "coverage"):
        (tmp_path / name).mkdir()

    scan = scan_repo(tmp_path)

    assert scan.top_level_dirs == ["src"]

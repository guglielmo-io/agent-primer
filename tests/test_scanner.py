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

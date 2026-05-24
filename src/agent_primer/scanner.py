from __future__ import annotations

import json
from pathlib import Path

from agent_primer.models import RepoScan, SymbolicArea


MANIFESTS = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "composer.json",
}
IGNORED_TOP_LEVEL_DIRS = {
    ".git",
    ".next",
    ".venv",
    "build",
    "coverage",
    "dist",
    "dist-server",
    "node_modules",
    "out",
}
NPM_DIRECT_SCRIPTS = {"start", "test", "restart", "stop"}


def scan_repo(root: Path) -> RepoScan:
    root = root.resolve()
    root_files = _root_files(root)
    top_level_dirs = _top_level_dirs(root)
    manifest_files = _manifest_files(root, root_files, top_level_dirs)
    commands: dict[str, str] = {}
    language_hints: list[str] = []
    package_manager = _detect_package_manager(root)

    if "package.json" in root_files:
        commands.update(_package_commands(root / "package.json", package_manager or "npm"))
        language_hints.append("TypeScript" if _has_ts_files(root) else "JavaScript")

    for manifest in manifest_files:
        if manifest == "package.json" or not manifest.endswith("/package.json"):
            continue
        prefix = manifest.removesuffix("/package.json")
        manifest_path = root / manifest
        nested_package_manager = _detect_package_manager(manifest_path.parent) or "npm"
        commands.update(_package_commands(manifest_path, nested_package_manager, prefix=prefix))
        language_hints.append("TypeScript" if _has_ts_files(manifest_path.parent) else "JavaScript")

    if "pyproject.toml" in root_files or "requirements.txt" in root_files:
        commands.update(_python_commands(root))
        language_hints.append("Python")

    return RepoScan(
        root_path=str(root),
        is_git_repo=(root / ".git").exists(),
        root_files=root_files,
        top_level_dirs=top_level_dirs,
        readme_files=_matching(root, ["README.md", "README.MD", "readme.md"]),
        ci_files=_ci_files(root),
        env_examples=_env_examples(root),
        docker_files=_docker_files(root),
        manifest_files=manifest_files,
        test_dirs=[name for name in top_level_dirs if name in {"test", "tests", "__tests__"}],
        source_dirs=[name for name in top_level_dirs if name in {"src", "app", "lib", "packages"}],
        existing_ai_docs=_existing_ai_docs(root),
        critical_files=_critical_files(root),
        language_hints=sorted(dict.fromkeys(language_hints)),
        commands=commands,
        package_manager=package_manager,
        symbolic_areas=_symbolic_areas(root),
    )


def _root_files(root: Path) -> list[str]:
    return sorted(path.name for path in root.iterdir() if path.is_file())


def _top_level_dirs(root: Path) -> list[str]:
    return sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".") and path.name not in IGNORED_TOP_LEVEL_DIRS
    )


def _manifest_files(root: Path, root_files: list[str], top_level_dirs: list[str]) -> list[str]:
    manifests = {name for name in root_files if name in MANIFESTS}
    for directory in top_level_dirs:
        package_json = root / directory / "package.json"
        if package_json.exists():
            manifests.add(_relative_path(package_json, root))
    return sorted(manifests)


def _matching(root: Path, names: list[str]) -> list[str]:
    return sorted(name for name in names if (root / name).exists())


def _ci_files(root: Path) -> list[str]:
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.exists():
        return []
    return sorted(_relative_path(path, root) for path in workflow_dir.glob("*.y*ml"))


def _env_examples(root: Path) -> list[str]:
    patterns = [".env.example", ".env.sample", "*.env.example"]
    matches: set[str] = set()
    for pattern in patterns:
        matches.update(_relative_path(path, root) for path in root.glob(pattern))
    return sorted(matches)


def _docker_files(root: Path) -> list[str]:
    names = ["Dockerfile", "docker-compose.yml", "docker-compose.yaml", "compose.yml"]
    return _matching(root, names)


def _existing_ai_docs(root: Path) -> list[str]:
    paths = ["AGENTS.md"]
    docs_dir = root / "docs" / "ai"
    if docs_dir.exists():
        paths.extend(_relative_path(path, root) for path in docs_dir.glob("*.md"))
    return sorted(path for path in paths if (root / path).exists())


def _critical_files(root: Path) -> list[str]:
    candidates = [
        "package.json",
        "pyproject.toml",
        "prisma/schema.prisma",
        "supabase/config.toml",
        "src/middleware.ts",
        "src/middleware.js",
        "middleware.ts",
        "middleware.js",
    ]
    found = [path for path in candidates if (root / path).exists()]
    manifest_files = _manifest_files(root, _root_files(root), _top_level_dirs(root))
    return sorted(dict.fromkeys(found + manifest_files + _ci_files(root) + _env_examples(root)))


def _detect_package_manager(root: Path) -> str | None:
    if (root / "pnpm-lock.yaml").exists():
        return "pnpm"
    if (root / "yarn.lock").exists():
        return "yarn"
    if (root / "bun.lockb").exists():
        return "bun"
    if (root / "package-lock.json").exists() or (root / "package.json").exists():
        return "npm"
    return None


def _package_commands(package_json: Path, package_manager: str, prefix: str | None = None) -> dict[str, str]:
    data = json.loads(package_json.read_text(encoding="utf-8"))
    scripts = data.get("scripts", {})
    command_prefix = f"{prefix}:" if prefix else ""
    commands = {f"{command_prefix}install": _scoped_command(f"{package_manager} install", prefix)}
    for key in ("dev", "test", "lint", "typecheck", "build", "start"):
        if key in scripts:
            commands[f"{command_prefix}{key}"] = _scoped_command(_script_command(package_manager, key), prefix)
    return commands


def _script_command(package_manager: str, key: str) -> str:
    if package_manager == "npm" and key not in NPM_DIRECT_SCRIPTS:
        return f"npm run {key}"
    return f"{package_manager} {key}"


def _scoped_command(command: str, prefix: str | None) -> str:
    if not prefix:
        return command
    return f"cd {prefix} && {command}"


def _python_commands(root: Path) -> dict[str, str]:
    text = (root / "pyproject.toml").read_text(encoding="utf-8") if (root / "pyproject.toml").exists() else ""
    commands = {"test": "pytest"} if "[tool.pytest" in text or (root / "tests").exists() else {}
    if "[tool.ruff" in text:
        commands["lint"] = "ruff check ."
    if "[tool.mypy" in text:
        commands["typecheck"] = "mypy ."
    if "[build-system]" in text:
        commands["build"] = "python -m build"
    return commands


def _has_ts_files(root: Path) -> bool:
    for path in root.rglob("*"):
        if any(part in IGNORED_TOP_LEVEL_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix in {".ts", ".tsx"}:
            return True
    return False


def _symbolic_areas(root: Path) -> list[SymbolicArea]:
    patterns = {
        "Auth Boundary": [
            "middleware.*",
            "src/middleware.*",
            "src/**/auth/**/*",
            "src/**/session.*",
            "src/**/session/**/*",
        ],
        "API Routes": [
            "src/app/api/**/*",
            "src/pages/api/**/*",
            "app/api/**/*",
            "pages/api/**/*",
        ],
        "Database Layer": [
            "prisma/schema.prisma",
            "src/**/db.*",
            "src/**/database.*",
            "src/**/supabase.*",
            "supabase/config.toml",
        ],
        "Billing Flow": [
            "src/**/stripe.*",
            "src/**/billing/**/*",
            "src/**/webhook/**/*",
            "src/app/api/**/stripe/**/*",
        ],
        "Frontend Routes": [
            "src/app/**/*",
            "src/pages/**/*",
            "app/**/*",
            "pages/**/*",
        ],
        "Test Surface": [
            "tests/**/*",
            "test/**/*",
            "src/**/*.test.*",
            "src/**/*.spec.*",
        ],
        "CI Pipeline": [
            ".github/workflows/*.yml",
            ".github/workflows/*.yaml",
        ],
    }
    areas: list[SymbolicArea] = []
    for name, area_patterns in patterns.items():
        paths = _symbolic_matches(root, area_patterns)
        if paths:
            areas.append(SymbolicArea(name=name, paths=paths[:12], evidence=paths[:5]))
    return areas


def _symbolic_matches(root: Path, patterns: list[str]) -> list[str]:
    matches: set[str] = set()
    for pattern in patterns:
        for path in root.glob(pattern):
            if path.is_file():
                matches.add(_relative_path(path, root))
    return sorted(matches)


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()

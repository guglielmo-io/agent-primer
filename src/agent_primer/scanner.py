from __future__ import annotations

import json
from pathlib import Path

from agent_primer.models import RepoScan, SymbolicArea


MANIFESTS = {
    "package.json",
    "pnpm-workspace.yaml",
    "pnpm-workspace.yml",
    "turbo.json",
    "nx.json",
    "pyproject.toml",
    "requirements.txt",
    "uv.lock",
    "poetry.lock",
    "Pipfile",
    "Pipfile.lock",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.work",
    "pom.xml",
    "mvnw",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "gradlew",
    "composer.json",
    "composer.lock",
    "Gemfile",
    "Gemfile.lock",
    "Makefile",
    "makefile",
    "justfile",
    "Justfile",
    "Taskfile.yml",
    "Taskfile.yaml",
}
MANIFEST_SUFFIXES = {".csproj", ".fsproj", ".vbproj", ".sln"}
IGNORED_TOP_LEVEL_DIRS = {
    ".git",
    ".gradle",
    ".next",
    ".turbo",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "dist-server",
    "node_modules",
    "out",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
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
        manifest_path = root / manifest
        manifest_name = manifest_path.name
        prefix = manifest.rsplit("/", 1)[0] if "/" in manifest else None
        if manifest == "package.json":
            continue
        if manifest.endswith("/package.json"):
            nested_package_manager = _detect_package_manager(manifest_path.parent) or "npm"
            commands.update(_package_commands(manifest_path, nested_package_manager, prefix=prefix))
            language_hints.append("TypeScript" if _has_ts_files(manifest_path.parent) else "JavaScript")
            continue
        if prefix and manifest_name in {"requirements.txt", "pyproject.toml"}:
            commands.update(_python_commands(root / prefix, project_root=root, prefix=prefix))
            language_hints.append("Python")
            continue
        if manifest_name in {"go.mod", "go.work"}:
            commands.update(_go_commands(prefix))
            language_hints.append("Go")
            continue
        if manifest_name == "Cargo.toml":
            commands.update(_rust_commands(prefix))
            language_hints.append("Rust")
            continue
        if manifest_name == "pom.xml":
            commands.update(_maven_commands(root / (prefix or "."), prefix))
            language_hints.append("Java")
            continue
        if manifest_name in {"build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"}:
            commands.update(_gradle_commands(root / (prefix or "."), prefix))
            language_hints.append("Java")
            continue
        if manifest_name.endswith((".csproj", ".fsproj", ".vbproj", ".sln")):
            commands.update(_dotnet_commands(prefix))
            language_hints.append(".NET")
            continue
        if manifest_name == "composer.json":
            commands.update(_composer_commands(manifest_path, prefix))
            language_hints.append("PHP")
            continue
        if manifest_name == "Gemfile":
            commands.update(_ruby_commands(root / (prefix or "."), prefix))
            language_hints.append("Ruby")
            continue
        if manifest_name in {"Makefile", "makefile"}:
            commands.update(_make_commands(manifest_path, prefix))
            continue
        if manifest_name in {"justfile", "Justfile"}:
            commands.update(_just_commands(manifest_path, prefix))
            continue
        if manifest_name in {"Taskfile.yml", "Taskfile.yaml"}:
            commands.update(_taskfile_commands(manifest_path, prefix))
            continue

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
        source_dirs=_source_dirs(root, top_level_dirs),
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


def _source_dirs(root: Path, top_level_dirs: list[str]) -> list[str]:
    source_dirs = {
        name
        for name in top_level_dirs
        if name
        in {
            "api",
            "app",
            "backend",
            "client",
            "cmd",
            "crates",
            "frontend",
            "internal",
            "lib",
            "packages",
            "pkg",
            "server",
            "service",
            "services",
            "src",
            "web",
            "worker",
            "workers",
        }
    }
    for directory in top_level_dirs:
        if directory in {"test", "tests", "__tests__", "docs"}:
            continue
        if any(path.suffix == ".py" and not _is_ignored_path(path, root) for path in (root / directory).rglob("*.py")):
            source_dirs.add(directory)
    return sorted(source_dirs)


def _manifest_files(root: Path, root_files: list[str], top_level_dirs: list[str]) -> list[str]:
    manifests = {name for name in root_files if _is_manifest_file(root / name)}
    for path in root.rglob("*"):
        if not path.is_file() or not _is_manifest_file(path) or _is_ignored_path(path, root):
            continue
        manifests.add(_relative_path(path, root))
    for directory in top_level_dirs:
        package_json = root / directory / "package.json"
        if package_json.exists():
            manifests.add(_relative_path(package_json, root))
    return sorted(manifests)


def _matching(root: Path, names: list[str]) -> list[str]:
    return sorted(name for name in names if (root / name).exists())


def _ci_files(root: Path) -> list[str]:
    matches = [
        path
        for path in [
            root / ".gitlab-ci.yml",
            root / ".gitlab-ci.yaml",
            root / "woodpecker.yml",
            root / "woodpecker.yaml",
            root / ".woodpecker.yml",
            root / ".woodpecker.yaml",
        ]
        if path.exists()
    ]
    workflow_dir = root / ".github" / "workflows"
    if workflow_dir.exists():
        matches.extend(workflow_dir.glob("*.y*ml"))
    gitea_workflow_dir = root / ".gitea" / "workflows"
    if gitea_workflow_dir.exists():
        matches.extend(gitea_workflow_dir.glob("*.y*ml"))
    return sorted(_relative_path(path, root) for path in matches)


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


def _is_manifest_file(path: Path) -> bool:
    return path.name in MANIFESTS or path.suffix in MANIFEST_SUFFIXES


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
    if command.startswith("npm run "):
        return f"npm --prefix {prefix} run {command.removeprefix('npm run ')}"
    if command.startswith("npm "):
        return f"npm --prefix {prefix} {command.removeprefix('npm ')}"
    return f"cd {prefix} && {command}"


def _python_commands(root: Path, project_root: Path | None = None, prefix: str | None = None) -> dict[str, str]:
    text = (root / "pyproject.toml").read_text(encoding="utf-8") if (root / "pyproject.toml").exists() else ""
    test_root = project_root or root
    command_prefix = f"{prefix}:" if prefix else ""
    commands: dict[str, str] = {}
    if "[tool.pytest" in text:
        test_command = "pytest"
        commands[f"{command_prefix}test"] = f"PYTHONPATH={prefix} {test_command}" if prefix else test_command
    elif (test_root / "tests").exists():
        test_command = "python -m unittest discover -s tests"
        commands[f"{command_prefix}test"] = f"PYTHONPATH={prefix} {test_command}" if prefix else test_command
    if "[tool.ruff" in text:
        commands[f"{command_prefix}lint"] = f"PYTHONPATH={prefix} ruff check ." if prefix else "ruff check ."
    if "[tool.mypy" in text:
        commands[f"{command_prefix}typecheck"] = f"PYTHONPATH={prefix} mypy ." if prefix else "mypy ."
    if "[build-system]" in text:
        commands[f"{command_prefix}build"] = f"cd {prefix} && python -m build" if prefix else "python -m build"
    return commands


def _go_commands(prefix: str | None = None) -> dict[str, str]:
    return {
        _stack_key("go", "test", prefix): _scope_shell("go test ./...", prefix),
        _stack_key("go", "vet", prefix): _scope_shell("go vet ./...", prefix),
    }


def _rust_commands(prefix: str | None = None) -> dict[str, str]:
    return {
        _stack_key("rust", "test", prefix): _scope_shell("cargo test", prefix),
        _stack_key("rust", "build", prefix): _scope_shell("cargo build", prefix),
    }


def _maven_commands(root: Path, prefix: str | None = None) -> dict[str, str]:
    maven = "./mvnw" if (root / "mvnw").exists() else "mvn"
    return {
        _stack_key("maven", "test", prefix): _scope_shell(f"{maven} test", prefix),
        _stack_key("maven", "package", prefix): _scope_shell(f"{maven} package", prefix),
    }


def _gradle_commands(root: Path, prefix: str | None = None) -> dict[str, str]:
    gradle = "./gradlew" if (root / "gradlew").exists() else "gradle"
    return {
        _stack_key("gradle", "test", prefix): _scope_shell(f"{gradle} test", prefix),
        _stack_key("gradle", "build", prefix): _scope_shell(f"{gradle} build", prefix),
    }


def _dotnet_commands(prefix: str | None = None) -> dict[str, str]:
    return {
        _stack_key("dotnet", "test", prefix): _scope_shell("dotnet test", prefix),
        _stack_key("dotnet", "build", prefix): _scope_shell("dotnet build", prefix),
    }


def _composer_commands(composer_json: Path, prefix: str | None = None) -> dict[str, str]:
    commands = {_stack_key("composer", "install", prefix): _scope_shell("composer install", prefix)}
    try:
        scripts = json.loads(composer_json.read_text(encoding="utf-8")).get("scripts", {})
    except json.JSONDecodeError:
        scripts = {}
    for script in ("test", "lint", "analyse", "analyze"):
        if script in scripts:
            commands[_stack_key("composer", script, prefix)] = _scope_shell(f"composer {script}", prefix)
    return commands


def _ruby_commands(root: Path, prefix: str | None = None) -> dict[str, str]:
    commands = {_stack_key("bundle", "install", prefix): _scope_shell("bundle install", prefix)}
    if (root / "spec").exists():
        commands[_stack_key("ruby", "test", prefix)] = _scope_shell("bundle exec rspec", prefix)
    elif (root / "test").exists():
        commands[_stack_key("ruby", "test", prefix)] = _scope_shell("bundle exec rake test", prefix)
    return commands


def _make_commands(makefile: Path, prefix: str | None = None) -> dict[str, str]:
    return {
        _stack_key("make", target, prefix): _scope_shell(f"make {target}", prefix)
        for target in _targets_from_makefile(makefile)
        if target in {"test", "lint", "check", "build"}
    }


def _just_commands(justfile: Path, prefix: str | None = None) -> dict[str, str]:
    return {
        _stack_key("just", target, prefix): _scope_shell(f"just {target}", prefix)
        for target in _targets_from_recipe_file(justfile)
        if target in {"test", "lint", "check", "build"}
    }


def _taskfile_commands(taskfile: Path, prefix: str | None = None) -> dict[str, str]:
    return {
        _stack_key("task", target, prefix): _scope_shell(f"task {target}", prefix)
        for target in _targets_from_taskfile(taskfile)
        if target in {"test", "lint", "check", "build"}
    }


def _targets_from_makefile(makefile: Path) -> set[str]:
    targets: set[str] = set()
    for line in makefile.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith(("\t", ".", "#")):
            continue
        if ":" not in line:
            continue
        target = line.split(":", 1)[0].strip()
        if target.replace("-", "").replace("_", "").isalnum():
            targets.add(target)
    return targets


def _targets_from_recipe_file(recipe_file: Path) -> set[str]:
    targets: set[str] = set()
    for line in recipe_file.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line or line.startswith((" ", "\t", "#")) or ":" not in line:
            continue
        target = line.split(":", 1)[0].strip()
        if target.replace("-", "").replace("_", "").isalnum():
            targets.add(target)
    return targets


def _targets_from_taskfile(taskfile: Path) -> set[str]:
    targets: set[str] = set()
    in_tasks = False
    for line in taskfile.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip() == "tasks:":
            in_tasks = True
            continue
        if not in_tasks:
            continue
        if line.startswith("  ") and not line.startswith("    ") and ":" in line:
            target = line.split(":", 1)[0].strip()
            if target.replace("-", "").replace("_", "").isalnum():
                targets.add(target)
    return targets


def _stack_key(stack: str, action: str, prefix: str | None = None) -> str:
    key = f"{stack}:{action}"
    return f"{prefix}:{key}" if prefix else key


def _scope_shell(command: str, prefix: str | None = None) -> str:
    return f"cd {prefix} && {command}" if prefix else command


def _has_ts_files(root: Path) -> bool:
    for path in root.rglob("*"):
        if _is_ignored_path(path, root):
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
            ".gitea/workflows/*.yml",
            ".gitea/workflows/*.yaml",
            ".gitlab-ci.yml",
            ".gitlab-ci.yaml",
            "woodpecker.yml",
            "woodpecker.yaml",
            ".woodpecker.yml",
            ".woodpecker.yaml",
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
            if path.is_file() and (_is_explicit_hidden_pattern(pattern) or not _is_ignored_path(path, root)) and path.suffix != ".pyc":
                matches.add(_relative_path(path, root))
    return sorted(matches)


def _is_explicit_hidden_pattern(pattern: str) -> bool:
    return pattern.startswith(".")


def _is_ignored_path(path: Path, root: Path) -> bool:
    relative = path.relative_to(root)
    return any(part in IGNORED_TOP_LEVEL_DIRS or part.startswith(".") and part != ".github" for part in relative.parts)


def _relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()

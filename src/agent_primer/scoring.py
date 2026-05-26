from __future__ import annotations

from pathlib import Path

from agent_primer.context_pack import REQUIRED_FILES
from agent_primer.models import ContextPack, Finding, RepoScan, ScoreBreakdown
from agent_primer.scanner import scan_repo


FORBIDDEN_MARKERS = ("TODO", "TBD", "Lorem ipsum", "Fill this in")
TEMPLATE_MARKERS = ("AGENT_FILL:",)
GENERATED_REPO_MAP_DIRS = ("node_modules", "dist", "dist-server", "coverage")


def score_existing_context(root: Path) -> ScoreBreakdown:
    files: dict[str, str] = {}
    for relative_path in REQUIRED_FILES:
        path = root / relative_path
        if path.exists():
            files[relative_path] = path.read_text(encoding="utf-8")
    return score_context_pack(ContextPack(files=files), scan_repo(root))


def score_context_pack(pack: ContextPack, scan: RepoScan) -> ScoreBreakdown:
    findings: list[Finding] = []
    categories = {
        "file_pack_completeness": _file_score(pack, findings),
        "repository_specificity": _specificity_score(pack),
        "architecture_clarity": _doc_score(pack, "docs/ai/architecture.md"),
        "verification_quality": _verification_score(pack, scan, findings),
        "risk_constraints": _risk_score(pack),
        "repo_map_usefulness": _repo_map_score(pack, scan, findings),
        "prompt_quality": _doc_score(pack, "AGENTS.md"),
        "freshness_consistency": _freshness_score(pack, findings),
    }
    total = sum(categories.values())
    total = _apply_caps(total, pack, scan, findings)
    return ScoreBreakdown(total=total, ready=total >= 85 and not findings, categories=categories, findings=findings)


def _file_score(pack: ContextPack, findings: list[Finding]) -> int:
    missing = [path for path in REQUIRED_FILES if path not in pack.files]
    for path in missing:
        findings.append(Finding(severity="P0", code="missing_file", message=f"Missing {path}", recommended_action=f"Create {path}"))
    return round(15 * (len(REQUIRED_FILES) - len(missing)) / len(REQUIRED_FILES))


def _specificity_score(pack: ContextPack) -> int:
    joined = "\n".join(pack.files.values())
    score = 0
    if "Evidence" in joined:
        score += 6
    if "Not detected" not in joined:
        score += 4
    if len(joined) > 1200:
        score += 5
    return min(score, 15)


def _doc_score(pack: ContextPack, path: str) -> int:
    text = pack.files.get(path, "")
    if not text:
        return 0
    score = 4 if len(text) > 80 else 2
    if "Not detected" not in text:
        score += 4
    if "Evidence" in text or path == "docs/ai/repo-map.md":
        score += 2
    return min(score, 15 if "architecture" in path else 10)


def _verification_score(pack: ContextPack, scan: RepoScan, findings: list[Finding]) -> int:
    text = pack.files.get("docs/ai/verification.md", "")
    if not text:
        findings.append(Finding(severity="P0", code="missing_verification_doc", message="Verification doc is missing", recommended_action="Create docs/ai/verification.md"))
        return 0
    if not scan.commands and "Not detected" in text:
        findings.append(Finding(severity="P1", code="no_verification_commands", message="No reliable verification commands detected", recommended_action="Inspect manifests and CI"))
        return 8
    verification_commands = _verification_commands(scan.commands)
    stale_commands = _add_stale_verification_command_findings(text, verification_commands, findings)
    for name, command in verification_commands.items():
        if not _command_present(text, command) and command not in stale_commands:
            findings.append(Finding(
                severity="P1",
                code="missing_verification_command",
                message=f"Verification doc does not include detected command `{command}` for `{name}`",
                recommended_action=f"Add `{command}` to docs/ai/verification.md if it is still valid",
            ))
    matches = sum(1 for command in verification_commands.values() if _command_present(text, command))
    return min(20, 10 + matches * 3)


def _risk_score(pack: ContextPack) -> int:
    text = pack.files.get("docs/ai/constraints.md", "") + pack.files.get("docs/ai/risks.md", "")
    if not text:
        return 0
    score = 5 if len(text) > 100 else 2
    if "Not detected" not in text:
        score += 5
    return min(score, 10)


def _repo_map_score(pack: ContextPack, scan: RepoScan, findings: list[Finding]) -> int:
    text = pack.files.get("docs/ai/repo-map.md", "")
    if not text:
        findings.append(Finding(severity="P0", code="missing_repo_map", message="Repo map is missing", recommended_action="Create docs/ai/repo-map.md"))
        return 0
    score = 4 if len(text) > 120 else 2
    if "Critical Files" in text:
        score += 2
    if "Symbolic Areas" in text:
        score += 2
    for directory in GENERATED_REPO_MAP_DIRS:
        if _repo_map_lists_directory(text, directory):
            findings.append(Finding(
                severity="P1",
                code="generated_dir_in_repo_map",
                message=f"Repo map includes generated or dependency directory: {directory}",
                recommended_action=f"Remove {directory} from docs/ai/repo-map.md unless it is intentionally source-controlled",
            ))
    missing_areas = [area.name for area in scan.symbolic_areas if area.name not in text]
    for area_name in missing_areas:
        findings.append(Finding(
            severity="P1",
            code="missing_symbolic_area",
            message=f"Repo map misses symbolic area: {area_name}",
            recommended_action=f"Add {area_name} paths to docs/ai/repo-map.md",
        ))
    if not scan.symbolic_areas:
        score += 2
    if scan.symbolic_areas and not missing_areas:
        score += 2
    return min(score, 10)


def _freshness_score(pack: ContextPack, findings: list[Finding]) -> int:
    has_template_markers = False
    for path, text in pack.files.items():
        for marker in TEMPLATE_MARKERS:
            if marker not in text:
                continue
            has_template_markers = True
            findings.append(Finding(
                severity="P0",
                code="uncompiled_template",
                message=f"Uncompiled template marker `{marker}` found in {path}",
                recommended_action=f"Replace every `{marker}` section in {path} with verified repository evidence",
            ))
    joined = "\n".join(pack.files.values())
    generic_markers = [marker for marker in FORBIDDEN_MARKERS if marker in joined]
    for marker in generic_markers:
        findings.append(Finding(severity="P1", code="generic_marker", message=f"Generic marker found: {marker}", recommended_action="Replace generic text with repository evidence"))
    return 0 if generic_markers or has_template_markers else 5


def _apply_caps(total: int, pack: ContextPack, scan: RepoScan, findings: list[Finding]) -> int:
    if "AGENTS.md" not in pack.files:
        total = min(total, 69)
    if "docs/ai/repo-map.md" not in pack.files:
        total = min(total, 79)
    if not scan.commands:
        total = min(total, 74)
    if any(finding.code == "uncompiled_template" for finding in findings):
        total = min(total, 64)
    if any(finding.code == "generic_marker" for finding in findings):
        total = min(total, 82)
    if any(finding.code in {"missing_verification_command", "stale_verification_command"} for finding in findings):
        total = min(total, 82)
    if any(finding.code == "generated_dir_in_repo_map" for finding in findings):
        total = min(total, 84)
    if any(finding.code == "missing_symbolic_area" for finding in findings):
        total = min(total, 84)
    return total


def _verification_commands(commands: dict[str, str]) -> dict[str, str]:
    return {
        name: command
        for name, command in commands.items()
        if name.split(":")[-1] not in {"dev", "start"}
    }


def _add_stale_verification_command_findings(
    text: str,
    commands: dict[str, str],
    findings: list[Finding],
) -> set[str]:
    stale_commands: set[str] = set()
    for name, command in commands.items():
        stale_command = _stale_npm_command(command)
        if stale_command and stale_command in text:
            stale_commands.add(command)
            findings.append(Finding(
                severity="P1",
                code="stale_verification_command",
                message=f"Verification doc uses `{stale_command}` for `{name}`, but npm scripts require `{command}`",
                recommended_action=f"Replace `{stale_command}` with `{command}` in docs/ai/verification.md",
            ))
    return stale_commands


def _command_present(text: str, command: str) -> bool:
    return any(variant in text for variant in _command_variants(command))


def _command_variants(command: str) -> set[str]:
    variants = {command}
    if " python " in f" {command} ":
        variants.add(command.replace(" python ", " .venv/bin/python "))
        variants.add(command.replace(" python ", " python3 "))
    if command.startswith("python "):
        variants.add(command.replace("python ", ".venv/bin/python ", 1))
        variants.add(command.replace("python ", "python3 ", 1))
    if command.startswith("npm --prefix "):
        parts = command.split(" ")
        if len(parts) >= 4:
            prefix = parts[2]
            npm_args = " ".join(parts[3:])
            variants.add(f"cd {prefix} && npm {npm_args}")
    return variants


def _stale_npm_command(command: str) -> str | None:
    if command.startswith("npm run "):
        return command.replace("npm run ", "npm ", 1)
    if " && npm run " in command:
        return command.replace(" && npm run ", " && npm ", 1)
    return None


def _repo_map_lists_directory(text: str, directory: str) -> bool:
    return any(line.strip() == f"- {directory}" for line in text.splitlines())

from __future__ import annotations

from pathlib import Path

from agent_primer.context_pack import REQUIRED_FILES
from agent_primer.models import ContextPack, Finding, RepoScan, ScoreBreakdown
from agent_primer.scanner import scan_repo


FORBIDDEN_MARKERS = ("TODO", "TBD", "Lorem ipsum", "Fill this in")


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
    return ScoreBreakdown(total=total, ready=total >= 85 and not _blocking(findings), categories=categories, findings=findings)


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
    matches = sum(1 for command in scan.commands.values() if command in text)
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
    joined = "\n".join(pack.files.values())
    generic_markers = [marker for marker in FORBIDDEN_MARKERS if marker in joined]
    for marker in generic_markers:
        findings.append(Finding(severity="P1", code="generic_marker", message=f"Generic marker found: {marker}", recommended_action="Replace generic text with repository evidence"))
    return 0 if generic_markers else 5


def _apply_caps(total: int, pack: ContextPack, scan: RepoScan, findings: list[Finding]) -> int:
    if "AGENTS.md" not in pack.files:
        total = min(total, 69)
    if "docs/ai/repo-map.md" not in pack.files:
        total = min(total, 79)
    if not scan.commands:
        total = min(total, 74)
    if any(finding.code == "generic_marker" for finding in findings):
        total = min(total, 82)
    if any(finding.code == "missing_symbolic_area" for finding in findings):
        total = min(total, 88)
    return total


def _blocking(findings: list[Finding]) -> bool:
    return any(finding.severity == "P0" for finding in findings)

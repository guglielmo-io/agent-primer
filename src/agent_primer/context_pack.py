from __future__ import annotations

from pathlib import Path

from agent_primer.models import AiContextDraft, ContextPack, RepoScan


REQUIRED_FILES = [
    "AGENTS.md",
    "docs/ai/product.md",
    "docs/ai/context.md",
    "docs/ai/architecture.md",
    "docs/ai/verification.md",
    "docs/ai/constraints.md",
    "docs/ai/risks.md",
    "docs/ai/repo-map.md",
]


def build_context_pack(scan: RepoScan, draft: AiContextDraft) -> ContextPack:
    files = {
        "AGENTS.md": _agents_md(),
        "docs/ai/product.md": _product_md(draft),
        "docs/ai/context.md": _context_md(scan, draft),
        "docs/ai/architecture.md": _list_doc("Architecture", draft.architecture_notes),
        "docs/ai/verification.md": _verification_md(scan, draft),
        "docs/ai/constraints.md": _list_doc("Constraints", draft.constraints),
        "docs/ai/risks.md": _list_doc("Risks", draft.risks),
        "docs/ai/repo-map.md": _repo_map_md(scan, draft),
    }
    return ContextPack(files=files)


def build_existing_template_pack(scan: RepoScan) -> ContextPack:
    project_name = Path(scan.root_path).name or "Repository"
    files = {
        "AGENTS.md": _agents_md(),
        "docs/ai/product.md": _product_template(project_name, scan),
        "docs/ai/context.md": _context_template(scan),
        "docs/ai/architecture.md": _architecture_template(scan),
        "docs/ai/verification.md": _verification_template(scan),
        "docs/ai/constraints.md": _agent_fill_doc("Constraints", "Identify non-negotiable product, technical, security, deployment, and compatibility constraints."),
        "docs/ai/risks.md": _agent_fill_doc("Risks", "Identify the highest-risk failure modes for future coding agents and how to verify them."),
        "docs/ai/repo-map.md": _repo_map_template(scan),
    }
    return ContextPack(files=files)


def _agents_md() -> str:
    return """# Agent Instructions

## Operating Contract
- Read this file before editing.
- If docs contain `AGENT_FILL`, complete those sections from repository evidence before coding.
- Read `docs/ai/context.md` for repository context.
- Read `docs/ai/architecture.md` before changing cross-module behavior.
- Read `docs/ai/verification.md` before choosing commands.
- Treat code, tests, manifests, CI, and runtime config as source of truth.
- If documentation disagrees with code, trust code and report the mismatch.
- Make the smallest safe change. Do not refactor unrelated code.
- Preserve user changes.

## Done When
- Relevant verification was run or a concrete blocker was reported.
- Risks and residual uncertainty were stated.
- Durable project facts changed by the work were reflected in `docs/ai/*`.
"""


def _product_template(project_name: str, scan: RepoScan) -> str:
    return f"""# Product

## Project Name
{project_name}

## Summary
{_agent_fill("Inspect README files, package metadata, routes, tests, and docs to state what this product does. Do not guess.")}

## Users And Jobs
{_agent_fill("Identify primary users, core workflows, and business-critical outcomes from repository evidence.")}

## Evidence
- README files: {', '.join(scan.readme_files) or 'Not detected'}
- Root files: {', '.join(scan.root_files) or 'Not detected'}
"""


def _product_md(draft: AiContextDraft) -> str:
    return f"""# Product

## Project Name
{draft.project_name}

## Summary
{draft.product_summary}

## Evidence
- Generated from setup input and repository scan.
"""


def _context_template(scan: RepoScan) -> str:
    return f"""# Context

## Repository
{scan.root_path}

## Detected Evidence
- Root files: {', '.join(scan.root_files) or 'Not detected'}
- Manifests: {', '.join(scan.manifest_files) or 'Not detected'}
- CI files: {', '.join(scan.ci_files) or 'Not detected'}
- Environment examples: {', '.join(scan.env_examples) or 'Not detected'}
- Docker files: {', '.join(scan.docker_files) or 'Not detected'}
- Language hints: {', '.join(scan.language_hints) or 'Not detected'}

## Stack
{_agent_fill("Replace this section with verified languages, frameworks, runtimes, storage, queues, and external services. Do not guess.")}

## Local Development
{_agent_fill("Describe install, run, env setup, seed, migration, and local service requirements with exact commands where verified.")}
"""


def _context_md(scan: RepoScan, draft: AiContextDraft) -> str:
    stack = _bullets(draft.detected_stack)
    commands = _dict_bullets(scan.commands or draft.verification_commands)
    return f"""# Context

## Repository
{scan.root_path}

## Stack
{stack}

## Commands
{commands}

## Evidence
- Root files: {', '.join(scan.root_files) or 'Not detected'}
- Manifests: {', '.join(scan.manifest_files) or 'Not detected'}
- CI files: {', '.join(scan.ci_files) or 'Not detected'}
"""


def _architecture_template(scan: RepoScan) -> str:
    return f"""# Architecture

## System Shape
{_agent_fill("Describe the actual module boundaries, data flow, request flow, background jobs, and integration points from code evidence. Do not guess.")}

## Symbolic Areas
{_symbolic_area_md(scan)}

## Change Rules
{_agent_fill("List rules future agents must follow when touching shared contracts, state, persistence, auth, billing, or async workflows.")}
"""


def _verification_template(scan: RepoScan) -> str:
    return f"""# Verification

## Detected Commands
{_dict_bullets(scan.commands)}

## Verification Ladder
{_agent_fill("Replace this section with the narrow-to-broad command ladder future agents should run for common change types.")}

## Evidence
- Commands were detected from manifests and project config when available.
"""


def _verification_md(scan: RepoScan, draft: AiContextDraft) -> str:
    commands = scan.commands or draft.verification_commands
    return f"""# Verification

## Known Commands
{_dict_bullets(commands)}

## Verification Ladder
- Start with the narrowest relevant command.
- Run broader checks when touching shared behavior.
- Do not claim completion without command evidence or a blocker.

## Evidence
- Commands were detected from manifests and project config when available.
"""


def _repo_map_template(scan: RepoScan) -> str:
    return f"""# Repo Map

## Top-Level Directories
{_bullets(scan.top_level_dirs or ['Not detected'])}

## Source Directories
{_bullets(scan.source_dirs or ['Not detected'])}

## Test Directories
{_bullets(scan.test_dirs or ['Not detected'])}

## Critical Files
{_bullets(scan.critical_files or scan.manifest_files or scan.root_files[:5] or ['Not detected'])}

## Symbolic Areas
{_symbolic_area_md(scan)}

## Agent Navigation Notes
{_agent_fill("Map the highest-value entry points, ownership boundaries, and files future agents should inspect first for each major workflow.")}
"""


def _repo_map_md(scan: RepoScan, draft: AiContextDraft) -> str:
    source_dirs = scan.source_dirs or [name for name in scan.top_level_dirs if name in {"src", "app", "lib", "packages"}]
    test_dirs = scan.test_dirs or [name for name in scan.top_level_dirs if name in {"test", "tests", "__tests__"}]
    critical_files = scan.critical_files or scan.manifest_files or scan.root_files[:5]
    return f"""# Repo Map

## Top-Level Directories
{_bullets(scan.top_level_dirs or ['Not detected'])}

## Source Directories
{_bullets(source_dirs or ['Not detected'])}

## Test Directories
{_bullets(test_dirs or ['Not detected'])}

## Critical Files
{_bullets(critical_files or ['Not detected'])}

## Symbolic Areas
{_symbolic_area_md(scan)}

## Agent Notes
{_bullets(draft.repo_map)}
"""


def _agent_fill_doc(title: str, instruction: str) -> str:
    return f"""# {title}

{_agent_fill(instruction + " Do not guess; cite concrete repository evidence.")}

## Evidence
- Template generated from deterministic repository scan.
"""


def _list_doc(title: str, items: list[str]) -> str:
    return f"""# {title}

{_bullets(items or ['Not detected'])}

## Evidence
- Generated from repository scan and setup analysis.
"""


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _dict_bullets(items: dict[str, str]) -> str:
    if not items:
        return "- Not detected"
    return "\n".join(f"- {key}: `{value}`" for key, value in sorted(items.items()))


def _agent_fill(instruction: str) -> str:
    return f"> AGENT_FILL: {instruction}"


def _symbolic_area_md(scan: RepoScan) -> str:
    if not scan.symbolic_areas:
        return "- Not detected"
    sections = []
    for area in scan.symbolic_areas:
        paths = "\n".join(f"  - {path}" for path in area.paths)
        sections.append(f"- {area.name}\n{paths}")
    return "\n".join(sections)

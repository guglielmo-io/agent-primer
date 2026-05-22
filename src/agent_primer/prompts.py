from __future__ import annotations

from agent_primer.models import RepoScan


def new_project_planner_prompt(project_name: str, raw_idea: str) -> str:
    return f"""Return compact English JSON for an AI repository context pack.

Project name: {project_name}
Raw idea: {raw_idea}

Rules:
- Do not write application code.
- Mark assumptions as proposed, not detected.
- Do not include API keys or secrets.
- Return JSON only with keys: product_summary, detected_stack, architecture_notes, verification_commands, constraints, risks, repo_map, readiness_findings, recommended_prompt.
"""


def existing_repo_context_prompt(scan: RepoScan) -> str:
    return f"""Return compact English JSON for an AI repository context pack.

Use only this deterministic repository scan as evidence:
{scan.model_dump_json(indent=2)}

Rules:
- Use only provided scan evidence.
- Do not invent repository facts.
- Write "Not detected" for missing facts.
- Do not write application code.
- Return JSON only with keys: product_summary, detected_stack, architecture_notes, verification_commands, constraints, risks, repo_map, readiness_findings, recommended_prompt.
"""


def context_audit_prompt(scan: RepoScan, current_docs: dict[str, str]) -> str:
    return f"""Audit and repair an AI repository context pack.

Repository scan:
{scan.model_dump_json(indent=2)}

Current docs:
{current_docs}

Rules:
- Return English JSON only.
- Use code/config/test evidence over stale docs.
- Do not modify application code.
- Identify contradictions, missing verification paths, weak repo-map entries, and generic text.
"""

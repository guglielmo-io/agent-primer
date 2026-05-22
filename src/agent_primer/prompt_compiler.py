from __future__ import annotations

from agent_primer.models import ContextPack, ScoreBreakdown


def compile_new_project_validation_prompt(repo_path: str, pack: ContextPack) -> str:
    files = _file_list(pack)
    return f"""You are operating inside this new software project:
{repo_path}

The generated context is a provisional product and architecture plan, not final truth.

Context files:
{files}

Your task:
- Read AGENTS.md and docs/ai/*.md first.
- Do not blindly accept the generated plan.
- Validate the approach with current research, current ecosystem options, and recent market or library evidence.
- Identify whether a better approach, simpler architecture, stronger library, or safer product direction exists.
- If a better approach exists, update the context files before planning implementation.
- Ask at most one blocking question only if implementation quality depends on it.
- Do not write application code until the context is internally consistent.
- Report the final recommended approach, trade-offs, and first verification commands.
"""


def compile_existing_fill_prompt(repo_path: str, pack: ContextPack) -> str:
    files = _file_list(pack)
    return f"""You are operating inside this existing software repository:
{repo_path}

The setup tool created context templates only. Your task is to compile them from repository evidence.

Context files:
{files}

Rules:
- Read AGENTS.md first.
- Inspect code, tests, manifests, CI, README files, env examples, and runtime config.
- replace every AGENT_FILL section with verified repository-specific facts.
- Do not modify application code.
- Do not invent missing facts.
- Write "Not detected" only after checking likely evidence locations.
- Keep the docs compact and useful for future coding agents.
- Report updated files, remaining uncertainty, and recommended verification commands.
"""


def compile_universal_prompt(repo_path: str, mode: str, pack: ContextPack, score: ScoreBreakdown) -> str:
    files = _file_list(pack)
    return f"""You are operating inside this software repository:
{repo_path}

Mode that prepared this repository:
{mode}

Use the AI context pack before changing code.

Context files:
{files}

Operating rules:
- Read AGENTS.md first.
- Read docs/ai/context.md before planning.
- Read docs/ai/architecture.md before cross-module changes.
- Read docs/ai/verification.md before choosing commands.
- Verify context claims against code, tests, manifests, CI, and runtime config.
- If docs and code disagree, treat code as source of truth and report the mismatch.
- Do not modify application code unless the user explicitly asks for product work.
- Make the smallest safe change.
- Run the narrowest useful verification first.

Readiness score:
{score.total}/100

Next task:
Improve or use the context pack according to the user's request, preserving repository behavior and reporting verification evidence.
"""


def compile_repair_prompt(repo_path: str, score: ScoreBreakdown) -> str:
    findings = "\n".join(
        f"- {finding.severity} {finding.code}: {finding.message}. {finding.recommended_action}."
        for finding in score.findings
    ) or "- No specific findings were generated."
    return f"""You are operating inside this software repository:
{repo_path}

The AI context readiness score is {score.total}/100.

Your task is to repair the AI context pack only.

Findings:
{findings}

Rules:
- Do not modify application code.
- Inspect code, tests, manifests, CI, README files, env examples, and runtime config.
- Update AGENTS.md and docs/ai/*.md with verified repository-specific facts.
- Do not invent missing facts.
- Write "Not detected" only after checking likely evidence locations.
- Report updated files, remaining blockers, and recommended verification commands.
"""


def _file_list(pack: ContextPack) -> str:
    return "\n".join(f"- {path}" for path in sorted(pack.files))

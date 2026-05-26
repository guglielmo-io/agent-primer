from __future__ import annotations

from agent_primer.models import ContextPack, RepoScan, ScoreBreakdown


def compile_new_project_validation_prompt(repo_path: str, pack: ContextPack) -> str:
    files = _file_list(pack)
    return f"""You are operating inside this new software project:
{repo_path}

The generated context is a provisional product and architecture plan, not final truth. Your first job is to pressure-test it before any implementation work.

Context files:
{files}

Required validation workflow:
- Read AGENTS.md and docs/ai/*.md first.
- Do not blindly accept the generated plan.
- Inspect the current repo state, package manifests, generated docs, env examples, scripts, and any created source files.
- Validate the approach with current research, current ecosystem options, recent market evidence, and current library/framework trade-offs.
- Create exactly 5 proposals for the product and technical approach.
- For each proposal, score each proposal from 1 to 10 for product fit, implementation speed, maintainability, scalability, cost, security, and agent-buildability.
- Compare the 5 proposals directly and explain why another proposal could be better than the provisional plan, especially because of technology choices, framework maturity, ecosystem support, hosting/deployment complexity, or long-term maintainability.
- Select one winner and explain why it is the best implementation direction now.
- If a better approach exists, update the context files before planning implementation.
- Update AGENTS.md and docs/ai/*.md so the winning approach, rejected alternatives, key risks, verification commands, and repo map are internally consistent.
- Ask at most one blocking question only if implementation quality depends on it.
- Do not write application code until the context is internally consistent and the winning proposal is documented.
- Do not write application code unless the user explicitly asks you to start implementation after this validation pass.

Final response requirements:
- Show the 5 proposals with scores.
- Explain the winning approach and the strongest reason each rejected proposal lost.
- List context files updated.
- List first verification commands for the future implementation.
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
    ) or _category_gap_guidance(score)
    categories = "\n".join(f"- {name}: {value}" for name, value in sorted(score.categories.items())) or "- Not available"
    return f"""You are operating inside this software repository:
{repo_path}

The AI context readiness score is {score.total}/100.

Your task is to repair the AI context pack only. Do not edit product code.

Score breakdown:
{categories}

Findings:
{findings}

Review protocol:
- Read AGENTS.md first, then every docs/ai/*.md file.
- Search for uncompiled markers such as AGENT_FILL, TODO, TBD, placeholder prose, and stale "Not detected" claims.
- Inspect README files, package manifests, lockfiles, CI, Docker files, env examples, scripts, routes, API handlers, data files, and deployment config.
- Verify command syntax against the package manager. For npm package scripts, use `npm run <script>` except direct lifecycle commands such as `npm test` and `npm start`.
- Check nested packages such as api/package.json, packages/*/package.json, or apps/*/package.json when present.
- Compare docs/ai/repo-map.md against the real source tree. Remove dependency/build outputs such as node_modules, dist, dist-server, coverage, and caches.
- Keep the docs compact. Future coding agents pay for every token.

Universal evidence sweep:
- If Agent Primer did not detect commands, treat that as incomplete evidence, not proof that commands do not exist.
- Check common manifests and lockfiles: package.json, pnpm-workspace.yaml, turbo.json, nx.json, pyproject.toml, requirements.txt, uv.lock, poetry.lock, Cargo.toml, go.mod, pom.xml, build.gradle, build.gradle.kts, *.csproj, *.sln, composer.json, Gemfile.
- Check task runners and local automation: Makefile, justfile, Taskfile.yml, scripts/, bin/, tools/, docker-compose.yml, Dockerfile, entrypoint files, and README command sections.
- Check CI definitions: .github/workflows, .gitlab-ci.yml, .gitea/workflows, Woodpecker files, deployment config, and any checked-in pipeline scripts.
- Check nested project roots: apps/*, packages/*, services/*, api/*, web/*, backend/*, frontend/*, bot/*, workers/*, mcp-servers/*, crates/*, cmd/*, internal/*, pkg/*.
- For unsupported or custom stacks, copy only commands that are explicitly evidenced by manifests, CI, docs, or scripts. Do not invent commands to satisfy the score.
- If multiple command variants exist, prefer the command that works from the repository root, then document any required working directory or environment variable.

Rules:
- Do not modify application code.
- Inspect code, tests, manifests, CI, README files, env examples, and runtime config.
- Update AGENTS.md and docs/ai/*.md with verified repository-specific facts.
- Do not invent missing facts.
- Write "Not detected" only after checking likely evidence locations.
- Preserve any user-authored facts that are still true.

Acceptance criteria:
- No AGENT_FILL or placeholder sections remain.
- docs/ai/context.md names the actual stack, runtime services, local setup, and important env vars.
- docs/ai/architecture.md explains the real module boundaries, request/data flow, integrations, and change rules.
- docs/ai/verification.md contains executable commands with correct package-manager syntax and a narrow-to-broad verification ladder.
- docs/ai/repo-map.md points future agents to the highest-value files and excludes generated/dependency outputs.
- docs/ai/constraints.md and docs/ai/risks.md list concrete repository-specific constraints and failure modes.

Final response format:
- Files updated.
- Evidence inspected.
- Verification commands that are valid now.
- Remaining uncertainty or blockers.
"""


def build_ai_repair_prompt_request(
    repo_path: str,
    score: ScoreBreakdown,
    scan: RepoScan,
    local_repair_prompt: str,
) -> str:
    findings = "\n".join(
        f"- {finding.severity} {finding.code}: {finding.message}. {finding.recommended_action}."
        for finding in score.findings
    ) or _category_gap_guidance(score)
    return f"""You are a principal AI context engineer and repair-prompt reviewer.

Mission:
Generate the strongest possible repair prompt for the user's coding agent to repair this repository's AI context pack.

Hard boundary:
- Do not compile or edit the context files yourself.
- Do not modify product code.
- Your output is only the prompt that the user will paste into their coding agent inside the repository.
- The coding agent will perform repair from repository evidence.
- The repair prompt must be specific to the score, findings, scan evidence, and context-pack failure modes below.

Repository:
{repo_path}

Context readiness score:
{score.total}/100

Score categories:
{score.model_dump_json(indent=2)}

Findings or score gaps:
{findings}

Deterministic scan evidence:
{scan.model_dump_json(indent=2)}

Local deterministic repair prompt:
{_block(local_repair_prompt)}

Repair-prompt requirements:
- Preserve all useful hard rules from the local deterministic repair prompt.
- Prioritize the highest-impact context weaknesses first.
- Include a universal evidence sweep for unsupported or custom stacks.
- Make the downstream agent inspect AGENTS.md and every docs/ai/*.md file before editing.
- Make the downstream agent inspect code, tests, manifests, lockfiles, CI, Docker, env examples, scripts, README files, runtime config, and nested project roots.
- Require verified repository-specific facts only. Do not allow invented facts.
- Require "Not detected" only after likely evidence locations were checked.
- Require compact docs because future coding agents pay for every token.
- Require the downstream agent to report files updated, evidence inspected, valid verification commands, and remaining uncertainty.
- Keep the prompt concise enough to paste into a coding agent, but specific enough to prevent generic repair.

Return JSON only with exactly these keys:
{{
  "repair_prompt": "one final repair prompt, no markdown wrapper outside this string",
  "quality_analysis": {{
    "summary": "one short quality verdict",
    "score": 1,
    "why_this_prompt_is_specific": "short reason",
    "risks": ["remaining risk or uncertainty"]
  }}
}}
"""


def _category_gap_guidance(score: ScoreBreakdown) -> str:
    guidance = {
        "file_pack_completeness": (15, "Create every required context file and keep paths exactly as expected."),
        "repository_specificity": (15, "Add concrete stack, manifests, env vars, runtime services, and integration facts from repository evidence."),
        "architecture_clarity": (10, "Strengthen module boundaries, request/data flow, persistence, background jobs, integrations, and change rules."),
        "verification_quality": (16, "Add executable narrow-to-broad verification commands from manifests, tests, Docker files, and CI."),
        "risk_constraints": (10, "Add repository-specific constraints, secrets rules, external-service failure modes, and high-risk edit areas."),
        "repo_map_usefulness": (10, "Map source dirs, test dirs, critical files, symbolic areas, generated-output exclusions, and navigation notes."),
        "prompt_quality": (10, "Make AGENTS.md compact but explicit: context loading order, no product-code edits during repair, verification expectations, and done criteria."),
        "freshness_consistency": (5, "Remove stale generic markers and add a concise freshness note tied to the evidence inspected."),
    }
    lines = []
    for name, value in sorted(score.categories.items()):
        target, action = guidance.get(name, (0, "Review and strengthen this category from repository evidence."))
        if value < target:
            lines.append(f"- P1 score_gap_{name}: {name} is {value}/{target}. {action}")
    return "\n".join(lines) or "- No specific findings were generated."


def _file_list(pack: ContextPack) -> str:
    return "\n".join(f"- {path}" for path in sorted(pack.files))


def _block(text: str) -> str:
    return f"```text\n{text.strip()}\n```"

from __future__ import annotations

from pydantic import BaseModel

from agent_primer.models import Finding, ScoreBreakdown


class PromptUpgradeResult(BaseModel):
    message: str
    upgraded_prompt: str
    score: ScoreBreakdown


def upgrade_prompt(raw_prompt: str) -> PromptUpgradeResult:
    upgraded = _deterministic_upgrade(raw_prompt)
    return PromptUpgradeResult(
        message="Prompt upgraded.",
        upgraded_prompt=upgraded,
        score=score_prompt(upgraded),
    )


def score_prompt(prompt: str) -> ScoreBreakdown:
    text = prompt.strip()
    lower = text.lower()
    words = [word for word in text.replace("\n", " ").split(" ") if word]
    findings: list[Finding] = []

    categories = {
        "objective_clarity": _objective_score(lower, findings),
        "context_depth": _context_score(lower, words, findings),
        "constraints": _constraint_score(lower, findings),
        "output_format": _output_format_score(lower, findings),
        "verification_quality": _verification_score(lower, findings),
        "specificity": _specificity_score(words, findings),
        "ambiguity_control": _ambiguity_score(lower, findings),
    }
    total = sum(categories.values())
    if any(finding.severity == "P0" for finding in findings):
        total = min(total, 69)
    return ScoreBreakdown(total=total, ready=total >= 85 and not findings, categories=categories, findings=findings)


def build_prompt_revision_request(
    raw_prompt: str,
    current_prompt: str,
    revision_request: str,
    score: ScoreBreakdown,
) -> str:
    findings = "\n".join(
        f"- {finding.severity} {finding.code}: {finding.message}. {finding.recommended_action}."
        for finding in score.findings
    ) or "- No current findings."
    return f"""You are an expert prompt architect.

Revise the current upgraded prompt according to the user's revision request.

Hard rules:
- Return JSON only with exactly one key: upgraded_prompt.
- upgraded_prompt must contain one final prompt, not multiple prompt variants.
- Do not return an agent_prompt, optimized_prompt, checklist field, commentary, markdown wrapper, or explanation outside JSON.
- Keep any quality checklist inside the one final prompt.
- Preserve the user's original intent unless the revision request explicitly changes it.
- Make the prompt compatible with any capable AI assistant or coding agent.

Raw user prompt:
{_block(raw_prompt)}

Current upgraded prompt:
{_block(current_prompt)}

Current prompt score:
{score.model_dump_json(indent=2)}

Current findings:
{findings}

Revision request:
{_block(revision_request)}
"""


def _deterministic_upgrade(raw_prompt: str) -> str:
    clean = raw_prompt.strip()
    lower = clean.lower()
    if _is_research_architecture_request(lower):
        return _research_architecture_upgrade(clean)
    return _general_execution_upgrade(clean)


def _is_research_architecture_request(lower: str) -> bool:
    research_signals = ("research", "ricerca", "github", "repo", "repository", "viral", "benchmark", "compare", "confront")
    architecture_signals = ("integr", "approach", "approccio", "system", "sistema", "architecture", "architettura", "wiki")
    return any(signal in lower for signal in research_signals) and any(signal in lower for signal in architecture_signals)


def _research_architecture_upgrade(clean: str) -> str:
    return f"""You are a principal software architecture analyst and AI tooling researcher.

Mission:
Investigate the user's request below and produce an evidence-based recommendation about whether the referenced external projects should influence, replace, or be integrated into the current system.

Original user request:
{_block(clean)}

Grounding rules:
- Treat project names, popularity claims, and "better than the classic wiki approach" as hypotheses to verify, not facts.
- Use current primary sources when external information may have changed: GitHub repositories, official docs, release notes, issues, benchmark pages, and project websites. Cite links and publication or commit dates when available.
- Inspect the current local repository or product context before recommending integration. Identify the existing architecture, context/documentation workflow, extension points, constraints, and failure modes.
- Separate evidence from inference. Mark any assumption that cannot be verified from sources or local code.
- Do not recommend adopting a tool only because it is viral, newer, graph-based, or popular.

Execution workflow:
1. Identify the canonical external projects mentioned by the user. If names are ambiguous, list the candidates and choose the most likely ones with evidence.
2. Summarize what each external project actually does, its core data model, architecture, license, maturity, installation path, dependencies, maintenance health, and practical limits.
3. Map the current system's relevant workflow and architecture from the repository. Focus on context creation, knowledge retrieval, repository mapping, documentation, scoring, repair, and agent handoff behavior.
4. Compare the external projects against the current system on concrete criteria: retrieval quality, setup complexity, local-first behavior, maintainability, latency, cost, privacy, developer ergonomics, failure modes, and integration effort.
5. Create exactly 5 candidate approaches. Include at least: no adoption, lightweight inspiration only, partial integration, adapter/prototype, and deeper replacement or redesign when plausible.
6. Score each approach from 1 to 10 for expected value, implementation effort, risk, maintainability, performance impact, user experience, and strategic upside.
7. Choose one recommended path. Explain why the other four lose for this specific system.
8. If adoption is recommended, provide a phased implementation plan with files/modules to inspect first, prototype scope, acceptance criteria, rollback path, and verification commands.
9. If adoption is not recommended, extract the best ideas worth copying and propose a smaller alternative that improves the current system without unnecessary complexity.

Output format:
1. Executive verdict
2. Source evidence with links and dates
3. Current system summary
4. External project summaries
5. Comparison matrix
6. Five scored proposals
7. Recommended path and rationale
8. Implementation or non-adoption plan
9. Verification and benchmark plan
10. Risks, unknowns, and follow-up questions

Quality checklist:
- The answer is based on verified sources and current repository evidence.
- The recommendation is specific to this system, not a generic trend analysis.
- The five proposals are meaningfully different and scored with clear rationale.
- The final recommendation includes concrete next steps and verification.
- The answer avoids hype and calls out weak evidence, hidden cost, and maintenance risk.

Return one final answer in the most useful format for the inferred task."""


def _general_execution_upgrade(clean: str) -> str:
    return f"""You are a senior domain expert and execution-quality reviewer.

Mission:
Execute the user's request below and produce the strongest possible final answer. Do not merely rewrite the prompt.

Original user request:
{_block(clean)}

Grounding rules:
- Infer the real objective, audience, constraints, expected output, and success criteria from the request.
- Ask at most one concise clarifying question only if a missing detail blocks a useful answer. Otherwise, state assumptions and proceed.
- Use current authoritative sources when facts, tools, prices, laws, model capabilities, benchmarks, or public repositories may have changed.
- Separate evidence from inference. Do not invent certainty.
- Avoid generic advice, filler, and unsupported claims.

Execution workflow:
1. Restate the real objective in one sentence.
2. Identify missing context, ambiguity, assumptions, risks, and decisions that could change the answer.
3. If useful, create exactly 5 candidate approaches. Score each from 1 to 10 for quality, feasibility, specificity, usefulness, risk control, and expected value.
4. Compare the approaches and choose the strongest one for this exact request.
5. Produce the final answer using the strongest approach with concrete steps, examples, trade-offs, and verification criteria where relevant.

Output format:
- Direct answer or executive verdict
- Evidence, assumptions, and constraints
- Options or approach comparison when useful
- Recommended path
- Concrete next steps
- Risks, edge cases, and verification checks

Quality checklist:
- The output satisfies the user's real intent, not only the literal wording.
- Assumptions are explicit when they affect the answer.
- The answer includes enough context, constraints, and decision criteria to be actionable.
- The output format is clear and appropriate for the task.
- Risks, edge cases, dependencies, or verification steps are handled when relevant.
- The answer removes unnecessary fluff and avoids generic advice.

Return one final answer in the most useful format for the inferred task."""


def _objective_score(lower: str, findings: list[Finding]) -> int:
    signals = ("create", "build", "write", "analyze", "fix", "improve", "generate", "plan", "compare", "explain")
    if any(signal in lower for signal in signals):
        return 18
    findings.append(Finding(
        severity="P1",
        code="weak_objective",
        message="The prompt does not state a clear action or objective",
        recommended_action="State what the AI should produce or decide",
    ))
    return 8


def _context_score(lower: str, words: list[str], findings: list[Finding]) -> int:
    if len(words) >= 80 or "context" in lower or "raw user request" in lower:
        return 15
    if len(words) >= 25:
        return 10
    findings.append(Finding(
        severity="P1",
        code="thin_prompt",
        message="The prompt is too short to carry reliable context",
        recommended_action="Add user intent, background, target audience, and relevant constraints",
    ))
    return 4


def _constraint_score(lower: str, findings: list[Finding]) -> int:
    signals = ("constraint", "must", "do not", "avoid", "require", "only", "without", "hard rules")
    if any(signal in lower for signal in signals):
        return 15
    findings.append(Finding(
        severity="P1",
        code="missing_constraints",
        message="The prompt does not define constraints or non-goals",
        recommended_action="Add must-have, must-avoid, and boundary conditions",
    ))
    return 5


def _output_format_score(lower: str, findings: list[Finding]) -> int:
    signals = ("format", "return", "output", "json", "markdown", "table", "final answer", "response")
    if any(signal in lower for signal in signals):
        return 15
    findings.append(Finding(
        severity="P1",
        code="missing_output_format",
        message="The prompt does not say what shape the answer should have",
        recommended_action="Specify the desired output format and sections",
    ))
    return 4


def _verification_score(lower: str, findings: list[Finding]) -> int:
    signals = ("verify", "test", "check", "score", "quality checklist", "criteria", "edge case", "risk")
    if any(signal in lower for signal in signals):
        return 15
    findings.append(Finding(
        severity="P1",
        code="missing_quality_gate",
        message="The prompt does not include quality or verification criteria",
        recommended_action="Add a checklist, scoring criteria, or verification steps",
    ))
    return 3


def _specificity_score(words: list[str], findings: list[Finding]) -> int:
    if len(words) >= 120:
        return 10
    if len(words) >= 40:
        return 7
    findings.append(Finding(
        severity="P1",
        code="low_specificity",
        message="The prompt leaves too much room for generic output",
        recommended_action="Add concrete domain, examples, desired depth, and constraints",
    ))
    return 3


def _ambiguity_score(lower: str, findings: list[Finding]) -> int:
    signals = ("assumption", "ambiguity", "missing context", "infer", "clarify", "decisions")
    if any(signal in lower for signal in signals):
        return 10
    findings.append(Finding(
        severity="P1",
        code="no_ambiguity_control",
        message="The prompt does not tell the AI how to handle ambiguity",
        recommended_action="Ask the AI to infer, state assumptions, and ask only blocking questions",
    ))
    return 3


def _block(text: str) -> str:
    return f"```text\n{text.strip()}\n```"

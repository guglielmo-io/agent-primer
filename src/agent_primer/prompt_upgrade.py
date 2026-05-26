from __future__ import annotations

from pydantic import BaseModel

from agent_primer.models import Finding, ScoreBreakdown


class PromptUpgradeResult(BaseModel):
    message: str
    upgraded_prompt: str
    score: ScoreBreakdown
    source: str = "local_fallback"
    ai_review: dict[str, object] | None = None


def upgrade_prompt(raw_prompt: str) -> PromptUpgradeResult:
    upgraded = _deterministic_upgrade(raw_prompt)
    return PromptUpgradeResult(
        message="Prompt upgraded locally.",
        upgraded_prompt=upgraded,
        score=score_prompt(upgraded),
    )


def build_ai_prompt_upgrade_request(raw_prompt: str, local_baseline: str) -> str:
    return f"""You are a principal prompt architect, domain strategist, and execution-quality reviewer.

Mission:
Generate the strongest possible single prompt for the raw user request below. The prompt must be custom to the request intent, not a fixed reusable template.

Raw user request:
{_block(raw_prompt)}

Local baseline prompt:
{_block(local_baseline)}

Universal prompt-quality rules:
- Infer the real objective, audience, constraints, expected output, success criteria, and hidden risks.
- Do not force one universal template.
- Choose the structure that fits the request. Do not force proposals, matrices, long workflows, research, or scoring when they are not useful.
- Use exactly 5 proposals only when the request is strategic, architectural, product-shaping, or materially benefits from comparing alternatives.
- For software work, include repository inspection, minimal-change execution, tests, verification, and final evidence.
- For writing work, prioritize final usable copy and tone control.
- For explanations, prioritize directness, examples, and caveats without unnecessary framework.
- For decisions, include criteria and alternatives only when they materially change the recommendation.
- For requests involving current facts, tools, laws, prices, benchmarks, public repositories, or model capabilities, instruct the target AI to use current authoritative sources and separate evidence from inference.
- Preserve the user's original intent and important wording. Do not invent missing facts.
- Keep the final prompt compatible with any capable AI assistant or coding agent.
- The final prompt should be as short as possible while still protecting quality.

Quality analysis:
- Analyze the absolute quality of your upgraded prompt before returning.
- Check intent fit, specificity, constraints, output shape, ambiguity handling, verification/research needs, and risk control.
- Revise the prompt internally if the analysis finds a weakness.

Return JSON only with exactly these keys:
{{
  "upgraded_prompt": "one final prompt, no markdown wrapper outside this string",
  "quality_analysis": {{
    "summary": "one short quality verdict",
    "score": 1,
    "intent_type": "software|decision|writing|explanation|research|general",
    "why_this_structure": "short reason",
    "risks": ["remaining risk or uncertainty"]
  }}
}}
"""


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
    if _is_software_execution_request(lower):
        return _software_execution_upgrade(clean)
    if _is_writing_request(lower):
        return _writing_upgrade(clean)
    if _is_explanation_request(lower):
        return _explanation_upgrade(clean)
    if _is_decision_request(lower):
        return _decision_upgrade(clean)
    return _general_execution_upgrade(clean)


def _is_research_architecture_request(lower: str) -> bool:
    research_signals = ("research", "ricerca", "github", "repo", "repository", "viral", "benchmark", "compare", "confront")
    architecture_signals = ("integr", "approach", "approccio", "system", "sistema", "architecture", "architettura", "wiki")
    return any(signal in lower for signal in research_signals) and any(signal in lower for signal in architecture_signals)


def _is_software_execution_request(lower: str) -> bool:
    action_signals = (
        "build",
        "create",
        "implement",
        "fix",
        "debug",
        "refactor",
        "test",
        "ship",
        "sviluppa",
        "crea",
        "implementa",
        "fai",
        "fixa",
        "sistema",
        "correggi",
        "debugga",
    )
    software_signals = (
        "app",
        "api",
        "bug",
        "code",
        "codice",
        "repo",
        "repository",
        "frontend",
        "backend",
        "database",
        "dashboard",
        "component",
        "workflow",
        "ci",
        "test",
    )
    return any(signal in lower for signal in action_signals) and any(signal in lower for signal in software_signals)


def _is_writing_request(lower: str) -> bool:
    action_signals = ("write", "draft", "rewrite", "email", "message", "copy", "scrivi", "riscrivi", "messaggio", "mail", "whatsapp", "linkedin")
    return any(signal in lower for signal in action_signals)


def _is_explanation_request(lower: str) -> bool:
    explanation_signals = ("explain", "spiega", "what does", "how does", "come funziona", "cosa vuol dire", "perché", "why")
    return any(signal in lower for signal in explanation_signals)


def _is_decision_request(lower: str) -> bool:
    decision_signals = ("should", "better", "best", "choose", "decide", "conviene", "meglio", "migliore", "sostituire", "replace", "worth")
    return any(signal in lower for signal in decision_signals)


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


def _software_execution_upgrade(clean: str) -> str:
    return f"""You are a principal software engineer and execution-quality reviewer.

Mission:
Execute the user's software request below with the smallest correct change and provide verified evidence. Do not merely discuss the request.

Original user request:
{_block(clean)}

Grounding rules:
- Infer the real engineering objective, affected surface, constraints, and success criteria from the request.
- Inspect the relevant repository files, tests, manifests, configuration, and existing patterns before changing anything.
- Ask at most one concise clarifying question only if a missing detail blocks a correct implementation. Otherwise, state assumptions and proceed.
- Preserve existing behavior and user changes. Do not perform unrelated refactors.
- Treat external input, generated text, secrets, and credentials as untrusted.

Execution workflow:
1. Identify the smallest relevant files, commands, and failure or success signal.
2. If this is a bug, reproduce or isolate the root cause before fixing when practical.
3. Implement the minimal change that satisfies the request and follows local project patterns.
4. Add or update focused tests when the behavior can reasonably be captured.
5. Run the narrowest useful verification first, then any broader check needed for the touched surface.
6. Self-review the diff for regressions, security issues, missing tests, and unintended scope.

Output format:
- Direct result summary.
- Files changed and why.
- Verification commands run with outcomes.
- Remaining risks, blockers, or follow-up checks.

Quality checklist:
- The solution addresses the root cause or requested behavior, not only a symptom.
- The change is scoped, maintainable, and consistent with the repository.
- Tests or verification are proportional to risk.
- No secrets, placeholders, dead code, unrelated refactors, or unsupported claims are introduced.

Return one final answer with implementation evidence."""


def _writing_upgrade(clean: str) -> str:
    return f"""You are a senior communications editor and intent-focused writing reviewer.

Mission:
Turn the user's request below into the strongest useful written output. Prioritize the final text the user can send or publish.

Original user request:
{_block(clean)}

Grounding rules:
- Infer audience, channel, tone, objective, constraints, and desired level of formality from the request.
- Ask at most one concise clarifying question only if the missing detail would materially change the text. Otherwise, state assumptions briefly and proceed.
- Preserve the user's factual claims unless they are clearly unsupported or risky.
- Avoid filler, exaggeration, generic phrasing, and over-formality.
- Use current sources only when factual claims may have changed or the text depends on current events, prices, policies, or public facts.

Execution workflow:
1. Identify the real communication goal and target reader.
2. Choose the most effective tone and structure for that goal.
3. Produce the final text first.
4. Include short alternatives only if they materially help the user choose tone or intensity.
5. Call out any factual assumptions or risky claims that should be verified before sending.

Output format:
- Final text.
- Optional shorter or stronger variant when useful.
- Notes on assumptions, tone, or facts to verify.

Quality checklist:
- The output is immediately usable.
- The tone fits the audience and channel.
- The text is specific, concise, and credible.
- Sensitive claims are hedged or marked for verification.

Return the final written output in the most useful format."""


def _explanation_upgrade(clean: str) -> str:
    return f"""You are a senior domain explainer and practical reasoning reviewer.

Mission:
Answer the user's question below clearly, accurately, and usefully. Do not turn a simple question into an unnecessary strategy document.

Original user request:
{_block(clean)}

Grounding rules:
- Infer what the user is actually trying to understand or decide.
- Ask at most one concise clarifying question only if the answer would otherwise be misleading.
- Use current authoritative sources when the answer depends on changing facts, tools, laws, prices, benchmarks, releases, or public repositories.
- Separate verified facts from assumptions and inference.
- Avoid generic advice, filler, and unnecessary frameworks.

Execution workflow:
1. Give the direct answer first.
2. Explain the reasoning in plain language with concrete examples where useful.
3. Cover important caveats, edge cases, or trade-offs.
4. Provide next steps only if they naturally follow from the question.

Output format:
- Direct answer.
- Short explanation.
- Caveats or examples.
- Practical next step when relevant.

Quality checklist:
- The answer is understandable without oversimplifying important details.
- Claims are calibrated to the available evidence.
- The response is no longer or more complex than the question requires.

Return one final answer."""


def _decision_upgrade(clean: str) -> str:
    return f"""You are a senior decision analyst and execution-quality reviewer.

Mission:
Decide the best path for the user's request below and explain the recommendation with enough evidence to act.

Original user request:
{_block(clean)}

Grounding rules:
- Infer the real decision, decision-maker, constraints, success criteria, and downside risks.
- Ask at most one concise clarifying question only if the decision cannot be useful without it. Otherwise, state assumptions and proceed.
- Use current authoritative sources when facts, tools, prices, laws, model capabilities, benchmarks, or public repositories may have changed.
- Separate evidence from inference and avoid certainty that the evidence does not support.
- Do not force a fixed number of proposals. Include alternatives only when they materially improve the decision.

Execution workflow:
1. State the decision in one sentence.
2. Identify assumptions, constraints, and decision criteria.
3. Compare viable options only if there is a real trade-off. Score or rank options when that improves clarity.
4. Recommend one path and explain why weaker options lose for this exact request.
5. Provide concrete next steps and verification checks.

Output format:
- Executive verdict.
- Evidence, assumptions, and constraints.
- Option comparison when useful.
- Recommended path.
- Concrete next steps.
- Risks and verification checks.

Quality checklist:
- The recommendation is specific to the user's situation.
- Trade-offs are explicit and practical.
- The answer avoids hype, generic advice, and false precision.
- Next steps are actionable.

Return one final answer in the most useful format."""


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
3. Choose the response structure that best fits the request. Do not force proposals, matrices, or long frameworks when a direct answer is better.
4. Compare alternatives only when the request involves a real decision or materially different paths.
5. Produce the final answer with concrete steps, examples, trade-offs, and verification criteria where relevant.

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
    signals = (
        "answer",
        "analyze",
        "build",
        "compare",
        "create",
        "decide",
        "draft",
        "execute",
        "explain",
        "fix",
        "generate",
        "implement",
        "improve",
        "produce",
        "recommend",
        "turn",
        "write",
    )
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

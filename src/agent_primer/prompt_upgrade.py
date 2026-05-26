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
    return f"""You are an expert prompt architect, domain strategist, and execution-quality reviewer.

Raw user request:
{_block(clean)}

Your task:
1. Infer the task type, domain, real objective, audience, constraints, expected output, and success criteria from the raw request. Do not ask the user to classify it.
2. Identify missing context, ambiguity, hidden assumptions, risks, and decisions that would materially change the best answer.
3. If useful, create exactly 5 candidate approaches. Score each from 1 to 10 for quality, feasibility, specificity, usefulness, risk control, and expected value.
4. Compare the candidate approaches and select the strongest one. Explain internally why weaker approaches lose before producing the final output.
5. Produce the final answer using the strongest approach. Be specific, structured, and directly useful. Avoid filler.

Quality checklist:
- The output satisfies the user's real intent, not only the literal wording.
- Assumptions are explicit when they affect the answer.
- The response includes enough context, constraints, and decision criteria to be actionable.
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

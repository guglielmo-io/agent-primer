from agent_primer.prompt_upgrade import (
    build_prompt_revision_request,
    score_prompt,
    upgrade_prompt,
)


def test_score_prompt_flags_plain_text_prompt_gaps():
    score = score_prompt("write me a website")

    assert score.ready is False
    assert score.total < 70
    assert any(finding.code == "thin_prompt" for finding in score.findings)
    assert any(finding.code == "missing_output_format" for finding in score.findings)
    assert any(finding.code == "missing_quality_gate" for finding in score.findings)


def test_upgrade_prompt_returns_one_copyable_enterprise_prompt():
    result = upgrade_prompt("Build a SaaS dashboard for managing invoices.")

    assert result.upgraded_prompt.count("Raw user request") == 1
    assert "Infer the task type" in result.upgraded_prompt
    assert "If useful, create exactly 5 candidate approaches" in result.upgraded_prompt
    assert "Quality checklist" in result.upgraded_prompt
    assert "Return one final answer" in result.upgraded_prompt
    assert result.score.ready is True
    assert result.score.total >= 85


def test_revision_request_preserves_single_prompt_output_contract():
    current = upgrade_prompt("Build a SaaS dashboard.").upgraded_prompt
    prompt = build_prompt_revision_request(
        raw_prompt="Build a SaaS dashboard.",
        current_prompt=current,
        revision_request="Make it stricter for coding agents.",
        score=score_prompt(current),
    )

    assert "Return JSON only" in prompt
    assert "upgraded_prompt" in prompt
    assert "one final prompt" in prompt
    assert "Make it stricter for coding agents." in prompt

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

    assert result.upgraded_prompt.count("Original user request") == 1
    assert "principal software engineer" in result.upgraded_prompt
    assert "Execute the user's software request below" in result.upgraded_prompt
    assert "smallest correct change" in result.upgraded_prompt
    assert "exactly 5 candidate approaches" not in result.upgraded_prompt
    assert "Quality checklist" in result.upgraded_prompt
    assert "Return one final answer" in result.upgraded_prompt
    assert "You are an expert prompt architect" not in result.upgraded_prompt
    assert result.score.ready is True
    assert result.score.total >= 85


def test_upgrade_prompt_specializes_research_architecture_requests():
    result = upgrade_prompt(
        "è uscita una repo di nome Openhuman e un sistema di nome Graphify virale su Github "
        "che sembra migliore dell'approccio classico Wiki in quanto più funzionale e avanzato, "
        "Fai una ricerca completa sul nostro sistema per capire come integrarlo o se conviene "
        "o se loro usano un approccio superiore."
    )

    assert "Openhuman" in result.upgraded_prompt
    assert "Graphify" in result.upgraded_prompt
    assert "GitHub" in result.upgraded_prompt or "github" in result.upgraded_prompt
    assert "current local repository" in result.upgraded_prompt
    assert "Comparison matrix" in result.upgraded_prompt
    assert "Create exactly 5 candidate approaches" in result.upgraded_prompt
    assert "Source evidence with links and dates" in result.upgraded_prompt
    assert "You are an expert prompt architect" not in result.upgraded_prompt
    assert result.score.ready is True


def test_upgrade_prompt_does_not_force_proposals_for_writing_requests():
    result = upgrade_prompt("Scrivimi un messaggio WhatsApp professionale per chiedere un aggiornamento.")

    assert "senior communications editor" in result.upgraded_prompt
    assert "Final text" in result.upgraded_prompt
    assert "exactly 5 candidate approaches" not in result.upgraded_prompt
    assert "Comparison matrix" not in result.upgraded_prompt
    assert result.score.ready is True


def test_upgrade_prompt_uses_direct_explanation_shape_for_explanation_requests():
    result = upgrade_prompt("Spiega in parole semplici come funziona questo tool.")

    assert "senior domain explainer" in result.upgraded_prompt
    assert "Direct answer" in result.upgraded_prompt
    assert "unnecessary strategy document" in result.upgraded_prompt
    assert "exactly 5 candidate approaches" not in result.upgraded_prompt
    assert result.score.ready is True


def test_upgrade_prompt_uses_decision_shape_without_fixed_proposal_count():
    result = upgrade_prompt("Secondo te è meglio sostituire il sistema attuale o migliorarlo?")

    assert "senior decision analyst" in result.upgraded_prompt
    assert "Do not force a fixed number of proposals" in result.upgraded_prompt
    assert "Recommended path" in result.upgraded_prompt
    assert "exactly 5 candidate approaches" not in result.upgraded_prompt
    assert result.score.ready is True


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

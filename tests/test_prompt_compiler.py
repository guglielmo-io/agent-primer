from agent_primer.models import ContextPack, Finding, ScoreBreakdown
from agent_primer.prompt_compiler import (
    compile_existing_fill_prompt,
    compile_new_project_validation_prompt,
    compile_repair_prompt,
    compile_universal_prompt,
)


def test_universal_prompt_contains_repo_files_and_no_placeholders():
    pack = ContextPack(files={"AGENTS.md": "# A", "docs/ai/context.md": "# C"})
    score = ScoreBreakdown(total=91, ready=True)

    prompt = compile_universal_prompt("/repo", "existing_project", pack, score)

    assert "/repo" in prompt
    assert "AGENTS.md" in prompt
    assert "docs/ai/context.md" in prompt
    assert "[" not in prompt
    assert "]" not in prompt


def test_repair_prompt_contains_score_and_no_app_code_instruction():
    score = ScoreBreakdown(total=64, ready=False)

    prompt = compile_repair_prompt("/repo", score)

    assert "64" in prompt
    assert "Do not modify application code" in prompt
    assert "repair" in prompt.lower()


def test_repair_prompt_contains_actionable_review_protocol():
    score = ScoreBreakdown(
        total=61,
        ready=False,
        categories={"verification_quality": 7, "repo_map_usefulness": 4},
        findings=[
            Finding(
                severity="P0",
                code="uncompiled_template",
                message="Uncompiled template marker found in docs/ai/context.md",
                recommended_action="Replace AGENT_FILL with verified repository evidence",
            ),
            Finding(
                severity="P1",
                code="stale_verification_command",
                message="Verification doc uses npm lint but package scripts require npm run lint",
                recommended_action="Replace npm lint with npm run lint",
            ),
        ],
    )

    prompt = compile_repair_prompt("/repo", score)

    assert "Score breakdown" in prompt
    assert "docs/ai/context.md" in prompt
    assert "npm run lint" in prompt
    assert "Acceptance criteria" in prompt
    assert "Final response format" in prompt


def test_repair_prompt_turns_low_category_scores_into_actions_without_findings():
    score = ScoreBreakdown(
        total=74,
        ready=False,
        categories={
            "verification_quality": 10,
            "architecture_clarity": 8,
            "prompt_quality": 8,
        },
    )

    prompt = compile_repair_prompt("/repo", score)

    assert "No specific findings were generated" not in prompt
    assert "score_gap_verification_quality" in prompt
    assert "executable narrow-to-broad verification commands" in prompt
    assert "score_gap_architecture_clarity" in prompt
    assert "score_gap_prompt_quality" in prompt


def test_repair_prompt_contains_universal_evidence_sweep_for_any_stack():
    score = ScoreBreakdown(total=74, ready=False, categories={"verification_quality": 8})

    prompt = compile_repair_prompt("/repo", score)

    assert "Universal evidence sweep" in prompt
    assert "Cargo.toml" in prompt
    assert "go.mod" in prompt
    assert "build.gradle" in prompt
    assert ".csproj" in prompt
    assert "Makefile" in prompt
    assert "If Agent Primer did not detect commands" in prompt


def test_existing_fill_prompt_orders_agent_to_compile_templates_only():
    pack = ContextPack(files={"AGENTS.md": "# A", "docs/ai/context.md": "AGENT_FILL"})

    prompt = compile_existing_fill_prompt("/repo", pack)

    assert "/repo" in prompt
    assert "AGENT_FILL" in prompt
    assert "Do not modify application code" in prompt
    assert "replace every AGENT_FILL section" in prompt


def test_new_project_prompt_forces_plan_challenge_and_research():
    pack = ContextPack(files={"AGENTS.md": "# A", "docs/ai/product.md": "# Product"})

    prompt = compile_new_project_validation_prompt("/repo/new-app", pack)

    assert "/repo/new-app" in prompt
    assert "provisional" in prompt
    assert "Do not blindly accept" in prompt
    assert "current research" in prompt
    assert "better approach" in prompt


def test_new_project_prompt_requires_five_scored_proposals():
    pack = ContextPack(files={"AGENTS.md": "# A", "docs/ai/product.md": "# Product"})

    prompt = compile_new_project_validation_prompt("/repo/new-app", pack)

    assert "Create exactly 5 proposals" in prompt
    assert "score each proposal from 1 to 10" in prompt
    assert "technology choices" in prompt
    assert "why another proposal could be better" in prompt
    assert "Do not write application code" in prompt

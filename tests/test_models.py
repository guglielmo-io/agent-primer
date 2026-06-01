from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_primer.models import AiContextDraft, SetupMode, SetupRequest


def test_new_project_requires_name_and_idea(tmp_path: Path):
    with pytest.raises(ValidationError):
        SetupRequest(
            mode=SetupMode.NEW_PROJECT,
            target_path=tmp_path,
            openrouter_model="google/gemini-3.5-flash",
        )


def test_project_name_allows_safe_characters_only(tmp_path: Path):
    with pytest.raises(ValidationError):
        SetupRequest(
            mode=SetupMode.NEW_PROJECT,
            target_path=tmp_path,
            project_name="../bad",
            raw_idea="Build a useful tool.",
            openrouter_model="google/gemini-3.5-flash",
        )


def test_project_name_normalizes_spaces_to_hyphens(tmp_path: Path):
    request = SetupRequest(
        mode=SetupMode.NEW_PROJECT,
        target_path=tmp_path,
        project_name="My Cool   Project",
        raw_idea="Build a useful tool.",
        openrouter_model="google/gemini-3.5-flash",
    )

    assert request.project_name == "My-Cool-Project"


def test_ai_context_draft_coerces_real_world_llm_shapes():
    # Shapes observed from a real OpenRouter response that previously crashed the
    # new-project flow: stack as a dict, commands as a list, repo_map nested.
    draft = AiContextDraft(
        project_name="Demo",
        product_summary="A demo app.",
        detected_stack={"frontend_framework": "React", "test": "Vitest"},
        verification_commands=["npm install", "npm run build"],
        repo_map={"src/": {"components/": "UI components"}},
    )

    assert draft.detected_stack == ["frontend_framework: React", "test: Vitest"]
    assert draft.verification_commands == {"1": "npm install", "2": "npm run build"}
    assert draft.repo_map == ["src/: components/: UI components"]


def test_existing_project_requires_existing_path(tmp_path: Path):
    missing_path = tmp_path / "missing"

    with pytest.raises(ValidationError):
        SetupRequest(
            mode=SetupMode.EXISTING_PROJECT,
            target_path=missing_path,
            openrouter_model="google/gemini-3.5-flash",
        )


def test_setup_request_model_defaults_when_no_api_model_is_needed(tmp_path: Path):
    request = SetupRequest(
        mode=SetupMode.EXISTING_PROJECT,
        target_path=tmp_path,
    )

    assert request.openrouter_model == "google/gemini-3.5-flash"

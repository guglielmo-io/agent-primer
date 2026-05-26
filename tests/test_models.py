from pathlib import Path

import pytest
from pydantic import ValidationError

from agent_primer.models import SetupMode, SetupRequest


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

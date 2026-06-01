from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator

from agent_primer.model_presets import DEFAULT_MODEL


class SetupMode(StrEnum):
    NEW_PROJECT = "new_project"
    EXISTING_PROJECT = "existing_project"
    VERIFY_REPAIR = "verify_repair"


class SetupRequest(BaseModel):
    mode: SetupMode
    target_path: Path
    project_name: str | None = None
    raw_idea: str | None = None
    openrouter_model: str = DEFAULT_MODEL
    overwrite: bool = False
    openrouter_api_key: str | None = None

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        # Natural input like "My Project" should just work: collapse internal
        # whitespace to hyphens before validating. Path separators and other
        # characters stay rejected so the name remains one safe directory segment.
        normalized = re.sub(r"\s+", "-", value.strip())
        if not normalized:
            return None
        if not re.fullmatch(r"[A-Za-z0-9_-]+", normalized):
            raise ValueError(
                "project_name may contain letters, numbers, spaces, hyphen, and underscore only"
            )
        return normalized

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> SetupRequest:
        if self.mode == SetupMode.NEW_PROJECT:
            if not self.project_name or not self.raw_idea:
                raise ValueError("new_project requires project_name and raw_idea")
            if not self.target_path.exists():
                raise ValueError("new_project target_path parent must exist")
        if (
            self.mode in {SetupMode.EXISTING_PROJECT, SetupMode.VERIFY_REPAIR}
            and not self.target_path.exists()
        ):
            raise ValueError(f"{self.mode.value} requires an existing target_path")
        return self


class ModelInfo(BaseModel):
    id: str
    name: str | None = None
    context_length: int | None = None
    pricing: dict[str, object] = Field(default_factory=dict)


class SymbolicArea(BaseModel):
    name: str
    paths: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class RepoScan(BaseModel):
    root_path: str
    is_git_repo: bool = False
    root_files: list[str] = Field(default_factory=list)
    top_level_dirs: list[str] = Field(default_factory=list)
    readme_files: list[str] = Field(default_factory=list)
    ci_files: list[str] = Field(default_factory=list)
    env_examples: list[str] = Field(default_factory=list)
    docker_files: list[str] = Field(default_factory=list)
    manifest_files: list[str] = Field(default_factory=list)
    test_dirs: list[str] = Field(default_factory=list)
    source_dirs: list[str] = Field(default_factory=list)
    existing_ai_docs: list[str] = Field(default_factory=list)
    critical_files: list[str] = Field(default_factory=list)
    language_hints: list[str] = Field(default_factory=list)
    commands: dict[str, str] = Field(default_factory=dict)
    package_manager: str | None = None
    symbolic_areas: list[SymbolicArea] = Field(default_factory=list)
    # Real dependency names parsed from root manifests, keyed by ecosystem
    # (python, node, go, rust). Ground truth so agents fill less of the stack by guesswork.
    dependencies: dict[str, list[str]] = Field(default_factory=dict)
    entry_points: list[str] = Field(default_factory=list)


def _flatten_scalar(value: object) -> str:
    if isinstance(value, dict):
        return ", ".join(f"{k}: {_flatten_scalar(v)}" for k, v in value.items())
    if isinstance(value, (list, tuple)):
        return ", ".join(_flatten_scalar(item) for item in value)
    return str(value)


def _as_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value] if value.strip() else []
    if isinstance(value, dict):
        return [f"{k}: {_flatten_scalar(v)}" for k, v in value.items()]
    if isinstance(value, (list, tuple)):
        items: list[str] = []
        for item in value:
            if isinstance(item, dict):
                items.extend(f"{k}: {_flatten_scalar(v)}" for k, v in item.items())
            else:
                items.append(str(item))
        return items
    return [str(value)]


def _as_str_dict(value: object) -> dict[str, str]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return {str(k): _flatten_scalar(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        commands: dict[str, str] = {}
        for index, item in enumerate(value, start=1):
            if isinstance(item, dict):
                commands.update({str(k): _flatten_scalar(v) for k, v in item.items()})
            else:
                commands[str(index)] = str(item)
        return commands
    return {"command": str(value)}


class AiContextDraft(BaseModel):
    project_name: str
    product_summary: str
    detected_stack: list[str] = Field(default_factory=list)
    architecture_notes: list[str] = Field(default_factory=list)
    verification_commands: dict[str, str] = Field(default_factory=dict)
    constraints: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    repo_map: list[str] = Field(default_factory=list)
    readiness_findings: list[str] = Field(default_factory=list)
    recommended_prompt: str = ""

    # LLMs return these fields with inconsistent shapes (a stack as a dict, commands
    # as a list, a nested repo map). Coerce to the documented shape so a usable AI
    # draft survives instead of crashing the new-project flow.
    @field_validator(
        "detected_stack",
        "architecture_notes",
        "constraints",
        "risks",
        "repo_map",
        "readiness_findings",
        mode="before",
    )
    @classmethod
    def _coerce_str_list(cls, value: object) -> list[str]:
        return _as_str_list(value)

    @field_validator("verification_commands", mode="before")
    @classmethod
    def _coerce_str_dict(cls, value: object) -> dict[str, str]:
        return _as_str_dict(value)

    @field_validator("product_summary", "recommended_prompt", mode="before")
    @classmethod
    def _coerce_str(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list, tuple)):
            return _flatten_scalar(value)
        return str(value)

    @classmethod
    def example(
        cls,
        project_name: str = "AI Ready Repository",
        product_idea: str | None = None,
    ) -> AiContextDraft:
        # Without an AI draft we still must carry the user's original idea into the
        # context files; otherwise the new project ships with a generic placeholder
        # summary and the idea is silently lost.
        idea = (product_idea or "").strip()
        summary = idea or (
            "Repository context pack generated for AI-assisted software engineering."
        )
        readiness = (
            "Provisional plan captured from the setup idea; verify and refine it against"
            " current research before implementation."
            if idea
            else "Context pack generated and ready for repository-specific review."
        )
        return cls(
            project_name=project_name,
            product_summary=summary,
            detected_stack=["Needs agent verification"],
            architecture_notes=["Use repository evidence before changing cross-module behavior."],
            verification_commands={"test": "Needs agent verification"},
            constraints=["Do not modify application code during context setup."],
            risks=["Stale documentation can mislead future agents."],
            repo_map=["Read root manifests, source directories, tests, and CI before editing."],
            readiness_findings=[readiness],
            recommended_prompt="Use the generated context files before editing code.",
        )


class ContextPack(BaseModel):
    files: dict[str, str]


class Finding(BaseModel):
    severity: str
    code: str
    message: str
    recommended_action: str


class ScoreBreakdown(BaseModel):
    total: int
    ready: bool
    categories: dict[str, int] = Field(default_factory=dict)
    findings: list[Finding] = Field(default_factory=list)


class WriteAction(BaseModel):
    action: str
    path: str


class WriteResult(BaseModel):
    actions: list[WriteAction]
    backup_path: str | None = None
    updated_files: list[str] = Field(default_factory=list)


class SetupResult(BaseModel):
    scan: RepoScan
    score: ScoreBreakdown
    context_pack: ContextPack
    planned_writes: list[WriteAction]
    universal_prompt: str
    repair_prompt: str | None = None
    write_result: WriteResult | None = None

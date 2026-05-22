from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field, field_validator, model_validator


class SetupMode(StrEnum):
    NEW_PROJECT = "new_project"
    EXISTING_PROJECT = "existing_project"
    VERIFY_REPAIR = "verify_repair"


class SetupRequest(BaseModel):
    mode: SetupMode
    target_path: Path
    project_name: str | None = None
    raw_idea: str | None = None
    openrouter_model: str
    overwrite: bool = False
    openrouter_api_key: str | None = None

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
            raise ValueError("project_name may contain letters, numbers, hyphen, and underscore only")
        return value

    @model_validator(mode="after")
    def validate_mode_requirements(self) -> "SetupRequest":
        if self.mode == SetupMode.NEW_PROJECT:
            if not self.project_name or not self.raw_idea:
                raise ValueError("new_project requires project_name and raw_idea")
            if not self.target_path.exists():
                raise ValueError("new_project target_path parent must exist")
        if self.mode in {SetupMode.EXISTING_PROJECT, SetupMode.VERIFY_REPAIR}:
            if not self.target_path.exists():
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

    @classmethod
    def example(cls, project_name: str = "AI Ready Repository") -> "AiContextDraft":
        return cls(
            project_name=project_name,
            product_summary="Repository context pack generated for AI-assisted software engineering.",
            detected_stack=["Needs agent verification"],
            architecture_notes=["Use repository evidence before changing cross-module behavior."],
            verification_commands={"test": "Needs agent verification"},
            constraints=["Do not modify application code during context setup."],
            risks=["Stale documentation can mislead future agents."],
            repo_map=["Read root manifests, source directories, tests, and CI before editing."],
            readiness_findings=["Context pack generated and ready for repository-specific review."],
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

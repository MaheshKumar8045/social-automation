from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SceneCharacterSemantic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    scene_role: Literal["visible", "referenced", "unknown"]
    physical_presence: bool
    evidence: str = ""
    reason: str = ""


class SceneDialogueSemantic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    speaker: str = ""
    text: str
    evidence: str


class SceneVisualMomentSemantic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    evidence: str
    priority: Literal["primary", "secondary"]


class SceneFactSemantic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str
    evidence: str


class SceneInferenceSemantic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    statement: str
    basis_evidence: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class SceneSemanticAnalysis(BaseModel):
    """LLM candidate semantics; deterministic validation happens after parsing."""

    model_config = ConfigDict(extra="forbid")

    summary: str
    primary_visual_moment: SceneVisualMomentSemantic
    secondary_visual_moment: SceneVisualMomentSemantic | None = None
    characters: list[SceneCharacterSemantic] = Field(default_factory=list)
    dialogue: list[SceneDialogueSemantic] = Field(default_factory=list)
    environment: list[SceneFactSemantic] = Field(default_factory=list)
    objects: list[SceneFactSemantic] = Field(default_factory=list)
    source_facts: list[SceneFactSemantic] = Field(default_factory=list)
    inferences: list[SceneInferenceSemantic] = Field(default_factory=list)


class SceneSemanticResult(BaseModel):
    """Validated semantics safe for downstream deterministic prompt composition."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ready", "rejected"]
    model: str
    llm_used: bool
    source_validated: bool
    analysis: SceneSemanticAnalysis | None = None
    rejected_reasons: list[str] = Field(default_factory=list)

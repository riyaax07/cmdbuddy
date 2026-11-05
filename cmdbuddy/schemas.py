"""Pydantic schemas for CmdBuddy structured AI responses and context validation."""

from __future__ import annotations

from typing import List, Literal, Optional
from pydantic import BaseModel, Field

RiskLevel = Literal["read-only", "write", "network", "destructive", "blocked"]
DiagnosisStatus = Literal["supported", "partially_supported", "insufficient_evidence"]


class GeneratedCommand(BaseModel):
    """An individual PowerShell command proposed by the AI."""
    command: str = Field(..., description="The exact PowerShell command to run.")
    explanation: str = Field(..., description="Brief explanation of what this command accomplishes.")
    risk: RiskLevel = Field("write", description="Risk level of the command.")
    requires_approval: bool = Field(True, description="Whether this command requires explicit user approval.")


class CommandGenerationResponse(BaseModel):
    """Structured response for intent-to-command generation."""
    summary: str = Field(..., description="High-level summary of the proposed solution.")
    commands: List[GeneratedCommand] = Field(default_factory=list, description="Ordered list of PowerShell commands.")
    limitations: List[str] = Field(default_factory=list, description="Known caveats, assumptions, or prerequisites.")
    relevant_files: List[str] = Field(default_factory=list, description="Relevant files inspected or affected.")


class EvidenceItem(BaseModel):
    """Specific evidence item grounded in a real project file."""
    file: str = Field(..., description="Relative path of the existing project file.")
    observation: str = Field(..., description="What was observed in this file.")


class DiagnosisResponse(BaseModel):
    """Strict schema for terminal error diagnosis."""
    summary: str = Field(..., description="Short summary of the diagnosis.")
    root_cause: str = Field(..., description="Identified root cause of the failure.")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0.")
    diagnosis_status: DiagnosisStatus = Field(..., description="Grounded status of diagnosis.")
    evidence: List[EvidenceItem] = Field(default_factory=list, description="File-based observations.")
    missing_information: List[str] = Field(default_factory=list, description="Information not found in context.")
    suggested_commands: List[GeneratedCommand] = Field(default_factory=list, description="Proposed remediation commands.")
    limitations: List[str] = Field(default_factory=list, description="Caveats or assumptions.")
    next_step_if_fix_fails: str = Field(..., description="Guidance if the suggested fix does not resolve the issue.")

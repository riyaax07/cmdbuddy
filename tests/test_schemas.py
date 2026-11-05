"""Unit tests for Pydantic schema validation."""

import pytest
from pydantic import ValidationError
from cmdbuddy.schemas import (
    CommandGenerationResponse,
    DiagnosisResponse,
    EvidenceItem,
    GeneratedCommand,
)


def test_command_generation_schema_valid():
    data = {
        "summary": "Scaffold React Vite application",
        "commands": [
            {
                "command": "npm create vite@latest ingreknow -- --template react-ts",
                "explanation": "Create new React Vite TypeScript template",
                "risk": "network",
                "requires_approval": True,
            },
            {
                "command": "cd ingreknow",
                "explanation": "Change directory",
                "risk": "read-only",
                "requires_approval": False,
            },
        ],
        "limitations": ["Requires Node 18+"],
        "relevant_files": ["package.json"],
    }
    resp = CommandGenerationResponse.model_validate(data)
    assert resp.summary == "Scaffold React Vite application"
    assert len(resp.commands) == 2
    assert resp.commands[0].risk == "network"
    assert resp.commands[1].risk == "read-only"


def test_command_generation_schema_invalid_risk():
    data = {
        "summary": "Invalid risk test",
        "commands": [
            {
                "command": "dir",
                "explanation": "Test",
                "risk": "super-safe",  # Not in Literal
            }
        ],
    }
    with pytest.raises(ValidationError):
        CommandGenerationResponse.model_validate(data)


def test_diagnosis_schema_valid():
    data = {
        "summary": "Missing dev script in package.json",
        "root_cause": "The package.json scripts object does not define a 'dev' script",
        "confidence": 0.95,
        "diagnosis_status": "supported",
        "evidence": [
            {
                "file": "package.json",
                "observation": "Scripts section contains 'build' and 'preview' but no 'dev'",
            }
        ],
        "missing_information": [],
        "suggested_commands": [
            {
                "command": 'npm pkg set scripts.dev="vite"',
                "explanation": "Add the dev script to package.json pointing to vite",
                "risk": "write",
                "requires_approval": True,
            }
        ],
        "limitations": [],
        "next_step_if_fix_fails": "Verify that vite is installed in devDependencies",
    }
    resp = DiagnosisResponse.model_validate(data)
    assert resp.diagnosis_status == "supported"
    assert resp.confidence == 0.95
    assert len(resp.evidence) == 1
    assert resp.suggested_commands[0].command == 'npm pkg set scripts.dev="vite"'


def test_diagnosis_schema_invalid_confidence():
    data = {
        "summary": "Out of range confidence test",
        "root_cause": "Error",
        "confidence": 1.5,  # Must be le=1.0
        "diagnosis_status": "supported",
        "next_step_if_fix_fails": "Check logs",
    }
    with pytest.raises(ValidationError):
        DiagnosisResponse.model_validate(data)

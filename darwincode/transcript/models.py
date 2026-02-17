from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SegmentType(Enum):
    THOUGHT = "thought"
    CODE_WRITE = "code_write"
    CODE_EDIT = "code_edit"
    CODE_READ = "code_read"
    COMMAND = "command"
    COMMAND_OUTPUT = "command_output"
    SEARCH = "search"
    ERROR = "error"


@dataclass
class TranscriptSegment:
    index: int
    type: SegmentType
    content: str
    timestamp: str
    metadata: dict = field(default_factory=dict)


@dataclass
class TranscriptSummary:
    total_segments: int
    thought_count: int
    files_written: list[str]
    files_edited: list[str]
    files_read: list[str]
    commands_run: list[str]
    errors: list[str]


@dataclass
class AgentTranscript:
    task_id: str
    agent_vendor: str
    generation: int
    started_at: str
    ended_at: str
    duration_seconds: float
    segments: list[TranscriptSegment]
    summary: TranscriptSummary

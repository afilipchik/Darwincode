from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from darwincode.transcript.models import (
    AgentTranscript,
    TranscriptSegment,
    TranscriptSummary,
)

logger = logging.getLogger(__name__)


class TranscriptParser(ABC):
    """Abstract parser for converting raw agent output into structured transcripts."""

    @abstractmethod
    def parse_raw(self, raw_lines: list[str]) -> list[TranscriptSegment]:
        """Parse raw JSONL lines into typed transcript segments."""
        ...

    def parse_file(
        self,
        raw_path: Path,
        task_id: str,
        agent_vendor: str,
        generation: int,
    ) -> AgentTranscript:
        """Parse a raw.jsonl file into a full AgentTranscript."""
        if not raw_path.exists():
            logger.warning("Raw transcript not found: %s", raw_path)
            return AgentTranscript(
                task_id=task_id,
                agent_vendor=agent_vendor,
                generation=generation,
                started_at="",
                ended_at="",
                duration_seconds=0,
                segments=[],
                summary=_empty_summary(),
            )

        lines = raw_path.read_text().strip().split("\n")
        lines = [l for l in lines if l.strip()]
        segments = self.parse_raw(lines)
        summary = _build_summary(segments)

        started_at = segments[0].timestamp if segments else ""
        ended_at = segments[-1].timestamp if segments else ""

        return AgentTranscript(
            task_id=task_id,
            agent_vendor=agent_vendor,
            generation=generation,
            started_at=started_at,
            ended_at=ended_at,
            duration_seconds=0,  # Filled by caller
            segments=segments,
            summary=summary,
        )

    def save_transcript(self, transcript: AgentTranscript, output_path: Path) -> None:
        """Save a structured transcript to JSON."""
        data = {
            "task_id": transcript.task_id,
            "agent_vendor": transcript.agent_vendor,
            "generation": transcript.generation,
            "started_at": transcript.started_at,
            "ended_at": transcript.ended_at,
            "duration_seconds": transcript.duration_seconds,
            "segments": [
                {
                    "index": s.index,
                    "type": s.type.value,
                    "content": s.content,
                    "timestamp": s.timestamp,
                    "metadata": s.metadata,
                }
                for s in transcript.segments
            ],
            "summary": {
                "total_segments": transcript.summary.total_segments,
                "thought_count": transcript.summary.thought_count,
                "files_written": transcript.summary.files_written,
                "files_edited": transcript.summary.files_edited,
                "files_read": transcript.summary.files_read,
                "commands_run": transcript.summary.commands_run,
                "errors": transcript.summary.errors,
            },
        }
        output_path.write_text(json.dumps(data, indent=2))


def _build_summary(segments: list[TranscriptSegment]) -> TranscriptSummary:
    from darwincode.transcript.models import SegmentType

    files_written = []
    files_edited = []
    files_read = []
    commands_run = []
    errors = []
    thought_count = 0

    for s in segments:
        path = s.metadata.get("path", "")
        if s.type == SegmentType.THOUGHT:
            thought_count += 1
        elif s.type == SegmentType.CODE_WRITE and path:
            files_written.append(path)
        elif s.type == SegmentType.CODE_EDIT and path:
            files_edited.append(path)
        elif s.type == SegmentType.CODE_READ and path:
            files_read.append(path)
        elif s.type == SegmentType.COMMAND:
            cmd = s.metadata.get("command", s.content[:100])
            commands_run.append(cmd)
        elif s.type == SegmentType.ERROR:
            errors.append(s.content[:200])

    return TranscriptSummary(
        total_segments=len(segments),
        thought_count=thought_count,
        files_written=list(dict.fromkeys(files_written)),
        files_edited=list(dict.fromkeys(files_edited)),
        files_read=list(dict.fromkeys(files_read)),
        commands_run=commands_run,
        errors=errors,
    )


def _empty_summary() -> TranscriptSummary:
    return TranscriptSummary(
        total_segments=0,
        thought_count=0,
        files_written=[],
        files_edited=[],
        files_read=[],
        commands_run=[],
        errors=[],
    )

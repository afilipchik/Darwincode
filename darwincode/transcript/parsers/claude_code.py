from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from darwincode.transcript.models import SegmentType, TranscriptSegment
from darwincode.transcript.parser import TranscriptParser

logger = logging.getLogger(__name__)

# Map Claude Code tool names to segment types
TOOL_TYPE_MAP = {
    "Write": SegmentType.CODE_WRITE,
    "Edit": SegmentType.CODE_EDIT,
    "Read": SegmentType.CODE_READ,
    "Bash": SegmentType.COMMAND,
    "Grep": SegmentType.SEARCH,
    "Glob": SegmentType.SEARCH,
    "NotebookEdit": SegmentType.CODE_EDIT,
}


class ClaudeCodeParser(TranscriptParser):
    """Parse Claude Code stream-json output into structured transcript segments."""

    def parse_raw(self, raw_lines: list[str]) -> list[TranscriptSegment]:
        segments: list[TranscriptSegment] = []
        index = 0

        for line in raw_lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            timestamp = datetime.now(timezone.utc).isoformat()

            event_type = event.get("type", "")

            if event_type == "assistant":
                # Assistant message — extract text blocks and tool_use blocks
                message = event.get("message", {})
                for block in message.get("content", []):
                    block_type = block.get("type", "")

                    if block_type == "text":
                        text = block.get("text", "")
                        if text.strip():
                            segments.append(TranscriptSegment(
                                index=index,
                                type=SegmentType.THOUGHT,
                                content=text,
                                timestamp=timestamp,
                            ))
                            index += 1

                    elif block_type == "tool_use":
                        tool_name = block.get("name", "")
                        tool_input = block.get("input", {})
                        seg_type = TOOL_TYPE_MAP.get(tool_name, SegmentType.COMMAND)

                        metadata = {"tool": tool_name}
                        content = ""

                        if seg_type == SegmentType.CODE_WRITE:
                            metadata["path"] = tool_input.get("file_path", "")
                            content = tool_input.get("content", "")
                        elif seg_type == SegmentType.CODE_EDIT:
                            metadata["path"] = tool_input.get("file_path", "")
                            metadata["old_string"] = tool_input.get("old_string", "")[:200]
                            content = tool_input.get("new_string", "")
                        elif seg_type == SegmentType.CODE_READ:
                            metadata["path"] = tool_input.get("file_path", "")
                            content = f"Read {metadata['path']}"
                        elif seg_type == SegmentType.COMMAND:
                            metadata["command"] = tool_input.get("command", "")
                            content = metadata["command"]
                        elif seg_type == SegmentType.SEARCH:
                            metadata["pattern"] = tool_input.get("pattern", "")
                            content = f"Search: {metadata.get('pattern', '')}"

                        segments.append(TranscriptSegment(
                            index=index,
                            type=seg_type,
                            content=content,
                            timestamp=timestamp,
                            metadata=metadata,
                        ))
                        index += 1

            elif event_type == "tool_result":
                # Tool result — capture as command output
                content_blocks = event.get("content", [])
                text_parts = []
                for block in content_blocks:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)

                if text_parts:
                    segments.append(TranscriptSegment(
                        index=index,
                        type=SegmentType.COMMAND_OUTPUT,
                        content="\n".join(text_parts),
                        timestamp=timestamp,
                    ))
                    index += 1

            elif event_type == "error":
                segments.append(TranscriptSegment(
                    index=index,
                    type=SegmentType.ERROR,
                    content=event.get("error", {}).get("message", str(event)),
                    timestamp=timestamp,
                ))
                index += 1

        return segments

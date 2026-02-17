import json

from darwincode.transcript.models import SegmentType
from darwincode.transcript.parsers.claude_code import ClaudeCodeParser


def _make_assistant_event(text: str | None = None, tool_use: dict | None = None):
    content = []
    if text:
        content.append({"type": "text", "text": text})
    if tool_use:
        content.append({"type": "tool_use", **tool_use})
    return json.dumps({"type": "assistant", "message": {"content": content}})


def _make_tool_result_event(text: str):
    return json.dumps({"type": "tool_result", "content": [{"type": "text", "text": text}]})


def test_parse_thought():
    parser = ClaudeCodeParser()
    lines = [_make_assistant_event(text="Let me analyze this code.")]
    segments = parser.parse_raw(lines)
    assert len(segments) == 1
    assert segments[0].type == SegmentType.THOUGHT
    assert "analyze" in segments[0].content


def test_parse_code_write():
    parser = ClaudeCodeParser()
    lines = [
        _make_assistant_event(tool_use={
            "name": "Write",
            "input": {"file_path": "src/main.py", "content": "print('hello')"},
        })
    ]
    segments = parser.parse_raw(lines)
    assert len(segments) == 1
    assert segments[0].type == SegmentType.CODE_WRITE
    assert segments[0].metadata["path"] == "src/main.py"
    assert "print" in segments[0].content


def test_parse_command():
    parser = ClaudeCodeParser()
    lines = [
        _make_assistant_event(tool_use={
            "name": "Bash",
            "input": {"command": "pytest tests/"},
        })
    ]
    segments = parser.parse_raw(lines)
    assert len(segments) == 1
    assert segments[0].type == SegmentType.COMMAND
    assert segments[0].metadata["command"] == "pytest tests/"


def test_parse_search():
    parser = ClaudeCodeParser()
    lines = [
        _make_assistant_event(tool_use={
            "name": "Grep",
            "input": {"pattern": "def foo"},
        })
    ]
    segments = parser.parse_raw(lines)
    assert len(segments) == 1
    assert segments[0].type == SegmentType.SEARCH


def test_parse_tool_result():
    parser = ClaudeCodeParser()
    lines = [_make_tool_result_event("10 passed, 2 failed")]
    segments = parser.parse_raw(lines)
    assert len(segments) == 1
    assert segments[0].type == SegmentType.COMMAND_OUTPUT
    assert "10 passed" in segments[0].content


def test_parse_mixed_conversation():
    parser = ClaudeCodeParser()
    lines = [
        _make_assistant_event(text="I'll fix the bug by editing main.py"),
        _make_assistant_event(tool_use={
            "name": "Read",
            "input": {"file_path": "src/main.py"},
        }),
        _make_tool_result_event("def add(a, b):\n    return a - b"),
        _make_assistant_event(text="I see the issue, it's using subtraction"),
        _make_assistant_event(tool_use={
            "name": "Edit",
            "input": {"file_path": "src/main.py", "old_string": "a - b", "new_string": "a + b"},
        }),
        _make_tool_result_event("File edited successfully"),
        _make_assistant_event(tool_use={
            "name": "Bash",
            "input": {"command": "pytest tests/"},
        }),
        _make_tool_result_event("1 passed"),
    ]
    segments = parser.parse_raw(lines)
    assert len(segments) == 8

    assert segments[0].type == SegmentType.THOUGHT
    assert segments[1].type == SegmentType.CODE_READ
    assert segments[2].type == SegmentType.COMMAND_OUTPUT
    assert segments[3].type == SegmentType.THOUGHT
    assert segments[4].type == SegmentType.CODE_EDIT
    assert segments[5].type == SegmentType.COMMAND_OUTPUT
    assert segments[6].type == SegmentType.COMMAND
    assert segments[7].type == SegmentType.COMMAND_OUTPUT


def test_parse_error_event():
    parser = ClaudeCodeParser()
    lines = [json.dumps({"type": "error", "error": {"message": "Rate limited"}})]
    segments = parser.parse_raw(lines)
    assert len(segments) == 1
    assert segments[0].type == SegmentType.ERROR
    assert "Rate limited" in segments[0].content

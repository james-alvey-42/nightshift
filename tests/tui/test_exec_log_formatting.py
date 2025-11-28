"""
Tests for exec log formatting helper functions
"""
import json
from pathlib import Path
from nightshift.interfaces.tui.controllers import (
    format_exec_log_from_result,
    extract_claude_text_from_result
)


def write_result(path, stdout_content):
    """Write a result file with given stdout content"""
    data = {"stdout": stdout_content}
    Path(path).write_text(json.dumps(data))


def test_format_exec_log_assistant_message(tmp_path):
    """Test formatting of assistant message events"""
    result_path = tmp_path / "result.json"

    # Assistant message with text content blocks
    events = [
        {
            "type": "assistant",
            "message": {
                "content": [
                    {"type": "text", "text": "First line\nSecond line"}
                ]
            }
        }
    ]
    stdout = "\n".join(json.dumps(e) for e in events)
    write_result(result_path, stdout)

    formatted = format_exec_log_from_result(str(result_path))

    assert "First line" in formatted
    assert "Second line" in formatted


def test_format_exec_log_tool_use(tmp_path):
    """Test formatting of tool_use events"""
    result_path = tmp_path / "result.json"

    events = [
        {
            "type": "tool_use",
            "name": "Read",
            "input": {"file_path": "/path/to/file.py"}
        }
    ]
    stdout = "\n".join(json.dumps(e) for e in events)
    write_result(result_path, stdout)

    formatted = format_exec_log_from_result(str(result_path))

    assert "🔧" in formatted
    assert "Read" in formatted
    assert "file_path" in formatted


def test_format_exec_log_tool_use_long_multiline_value(tmp_path):
    """Test that long multiline tool arguments are shown in full"""
    result_path = tmp_path / "result.json"

    # Create a multiline value
    long_content = "\n".join([f"line {i}" for i in range(100)])

    events = [
        {
            "type": "tool_use",
            "name": "Write",
            "input": {"file_path": "/test.py", "content": long_content}
        }
    ]
    stdout = "\n".join(json.dumps(e) for e in events)
    write_result(result_path, stdout)

    formatted = format_exec_log_from_result(str(result_path))

    # Should include all lines (no truncation)
    assert "line 0" in formatted
    assert "line 99" in formatted


def test_format_exec_log_result_success(tmp_path):
    """Test formatting of successful result events"""
    result_path = tmp_path / "result.json"

    events = [
        {
            "type": "result",
            "subtype": "success"
        }
    ]
    stdout = "\n".join(json.dumps(e) for e in events)
    write_result(result_path, stdout)

    formatted = format_exec_log_from_result(str(result_path))

    assert "✅" in formatted
    assert "success" in formatted.lower()


def test_format_exec_log_result_other_subtype(tmp_path):
    """Test formatting of non-success result events"""
    result_path = tmp_path / "result.json"

    events = [
        {
            "type": "result",
            "subtype": "error"
        }
    ]
    stdout = "\n".join(json.dumps(e) for e in events)
    write_result(result_path, stdout)

    formatted = format_exec_log_from_result(str(result_path))

    assert "Result:" in formatted or "error" in formatted


def test_format_exec_log_malformed_json(tmp_path):
    """Test that malformed JSON lines are handled gracefully"""
    result_path = tmp_path / "result.json"

    # Mix of valid and invalid JSON
    stdout = """{"type": "text", "text": "valid line"}
{invalid json here
{"type": "text", "text": "another valid line"}"""

    write_result(result_path, stdout)

    formatted = format_exec_log_from_result(str(result_path))

    # Should include valid lines
    assert "valid line" in formatted
    assert "another valid line" in formatted
    # Should include raw malformed line
    assert "{invalid json here" in formatted


def test_format_exec_log_no_truncation(tmp_path):
    """Test that output is not truncated - scrolling handles long content"""
    result_path = tmp_path / "result.json"

    # Create many lines of events
    events = [{"type": "text", "text": f"Line {i}"} for i in range(500)]
    stdout = "\n".join(json.dumps(e) for e in events)
    write_result(result_path, stdout)

    formatted = format_exec_log_from_result(str(result_path))

    # Should include all lines (no truncation marker)
    assert "Line 0" in formatted
    assert "Line 499" in formatted
    assert "not shown" not in formatted.lower()


def test_format_exec_log_empty_stdout(tmp_path):
    """Test handling of empty stdout"""
    result_path = tmp_path / "result.json"
    write_result(result_path, "")

    formatted = format_exec_log_from_result(str(result_path))

    assert formatted == ""


def test_format_exec_log_missing_file(tmp_path):
    """Test handling of missing result file"""
    result_path = tmp_path / "nonexistent.json"

    formatted = format_exec_log_from_result(str(result_path))

    assert formatted == ""


def test_extract_claude_text_from_result(tmp_path):
    """Test extraction of Claude text from content_block_delta events"""
    result_path = tmp_path / "result.json"

    # Stream-json format with content_block_delta events
    events = [
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello "}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "world"}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "!"}},
    ]
    stdout = "\n".join(json.dumps(e) for e in events)
    write_result(result_path, stdout)

    extracted = extract_claude_text_from_result(str(result_path))

    assert extracted == "Hello world!"


def test_extract_claude_text_mixed_events(tmp_path):
    """Test that only text_delta events are extracted"""
    result_path = tmp_path / "result.json"

    events = [
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Text 1"}},
        {"type": "other_event", "data": "ignored"},
        {"type": "content_block_delta", "delta": {"type": "other_delta"}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": " Text 2"}},
    ]
    stdout = "\n".join(json.dumps(e) for e in events)
    write_result(result_path, stdout)

    extracted = extract_claude_text_from_result(str(result_path))

    assert extracted == "Text 1 Text 2"


def test_extract_claude_text_missing_file(tmp_path):
    """Test extraction from missing file returns empty string"""
    result_path = tmp_path / "nonexistent.json"

    extracted = extract_claude_text_from_result(str(result_path))

    assert extracted == ""


def test_extract_claude_text_empty_stdout(tmp_path):
    """Test extraction from empty stdout returns empty string"""
    result_path = tmp_path / "result.json"
    write_result(result_path, "")

    extracted = extract_claude_text_from_result(str(result_path))

    assert extracted == ""

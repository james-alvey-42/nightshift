"""
Tests for SlackFormatter
"""
import pytest
from unittest.mock import Mock, MagicMock
from pathlib import Path
import json

from nightshift.integrations.slack_formatter import SlackFormatter


class TestFormatApprovalMessage:
    """Tests for format_approval_message"""

    def test_basic_approval_message(self):
        """format_approval_message creates header and buttons"""
        task = Mock()
        task.task_id = "task_001"
        task.description = "Test task description"
        task.allowed_tools = ["Read", "Write"]
        task.timeout_seconds = 300

        plan = {
            "enhanced_prompt": "Enhanced test",
            "allowed_tools": ["Read", "Write"]
        }

        blocks = SlackFormatter.format_approval_message(task, plan)

        # Check header
        assert blocks[0]["type"] == "header"
        assert "task_001" in blocks[0]["text"]["text"]

        # Check description section
        assert blocks[1]["type"] == "section"
        assert "Test task description" in blocks[1]["text"]["text"]

        # Check actions section with buttons
        actions_block = [b for b in blocks if b["type"] == "actions"][0]
        button_ids = [el["action_id"] for el in actions_block["elements"]]
        assert "approve_task_001" in button_ids
        assert "reject_task_001" in button_ids
        assert "details_task_001" in button_ids

    def test_long_description_truncated(self):
        """format_approval_message truncates long descriptions"""
        task = Mock()
        task.task_id = "task_001"
        task.description = "X" * 600  # Over 500 chars
        task.allowed_tools = []
        task.timeout_seconds = 300

        blocks = SlackFormatter.format_approval_message(task, {})

        description_block = blocks[1]["text"]["text"]
        assert len(description_block) < 600
        assert "..." in description_block

    def test_many_tools_truncated(self):
        """format_approval_message shows first 5 tools with count"""
        task = Mock()
        task.task_id = "task_001"
        task.description = "Test"
        task.allowed_tools = ["Tool1", "Tool2", "Tool3", "Tool4", "Tool5", "Tool6", "Tool7"]
        task.timeout_seconds = 300

        blocks = SlackFormatter.format_approval_message(task, {})

        # Find tools field
        fields_block = [b for b in blocks if b.get("type") == "section" and "fields" in b][0]
        tools_field = [f for f in fields_block["fields"] if "Tools" in f["text"]][0]

        assert "+2 more" in tools_field["text"]

    def test_timeout_display(self):
        """format_approval_message shows timeout in seconds and minutes"""
        task = Mock()
        task.task_id = "task_001"
        task.description = "Test"
        task.allowed_tools = []
        task.timeout_seconds = 900  # 15 minutes

        blocks = SlackFormatter.format_approval_message(task, {})

        # Find timeout field
        fields_block = [b for b in blocks if b.get("type") == "section" and "fields" in b][0]
        timeout_field = [f for f in fields_block["fields"] if "Timeout" in f["text"]][0]

        assert "900s" in timeout_field["text"]
        assert "15m" in timeout_field["text"]


class TestFormatCompletionNotification:
    """Tests for format_completion_notification"""

    def test_success_notification(self):
        """format_completion_notification shows success status"""
        summary = {
            "task_id": "task_001",
            "status": "success",
            "description": "Test task completed",
            "execution_time": 45.5,
            "token_usage": 1500
        }

        blocks = SlackFormatter.format_completion_notification(summary)

        # Check header shows success
        header = blocks[0]
        assert header["type"] == "header"
        assert "SUCCESS" in header["text"]["text"]
        assert "✅" in header["text"]["text"]

    def test_failed_notification(self):
        """format_completion_notification shows failure status"""
        summary = {
            "task_id": "task_001",
            "status": "failed",
            "description": "Test task",
            "execution_time": 10.0,
            "error_message": "Task timed out"
        }

        blocks = SlackFormatter.format_completion_notification(summary)

        header = blocks[0]
        assert "FAILED" in header["text"]["text"]
        assert "❌" in header["text"]["text"]

        # Check error message block exists
        error_blocks = [b for b in blocks if b.get("type") == "section" and
                       "Error" in b.get("text", {}).get("text", "")]
        assert len(error_blocks) > 0

    def test_file_changes_displayed(self):
        """format_completion_notification shows file changes"""
        summary = {
            "task_id": "task_001",
            "status": "success",
            "description": "Test",
            "execution_time": 30.0,
            "file_changes": {
                "created": ["new_file.py"],
                "modified": ["existing.py"],
                "deleted": ["old.py"]
            }
        }

        blocks = SlackFormatter.format_completion_notification(summary)

        # Find file changes block
        blocks_text = " ".join([str(b) for b in blocks])
        assert "Created" in blocks_text
        assert "Modified" in blocks_text
        assert "Deleted" in blocks_text

    def test_many_files_truncated(self):
        """format_completion_notification truncates long file lists"""
        summary = {
            "task_id": "task_001",
            "status": "success",
            "description": "Test",
            "execution_time": 30.0,
            "file_changes": {
                "created": [f"file_{i}.py" for i in range(10)],
                "modified": [],
                "deleted": []
            }
        }

        blocks = SlackFormatter.format_completion_notification(summary)

        blocks_text = " ".join([str(b) for b in blocks])
        # Should show "+X more" for files beyond 5
        assert "more" in blocks_text


class TestFormatTaskList:
    """Tests for format_task_list"""

    def test_empty_task_list(self):
        """format_task_list shows message for empty list"""
        blocks = SlackFormatter.format_task_list([])

        assert len(blocks) == 1
        assert "No tasks found" in blocks[0]["text"]["text"]

    def test_task_list_with_tasks(self):
        """format_task_list shows tasks"""
        task1 = Mock()
        task1.task_id = "task_001"
        task1.status = "STAGED"
        task1.description = "First task"

        task2 = Mock()
        task2.task_id = "task_002"
        task2.status = "RUNNING"
        task2.description = "Second task"

        blocks = SlackFormatter.format_task_list([task1, task2])

        # Header
        assert blocks[0]["type"] == "header"
        assert "Task Queue" in blocks[0]["text"]["text"]

        # Task entries
        assert len(blocks) >= 3  # Header + 2 tasks

    def test_task_list_with_status_filter(self):
        """format_task_list shows filter in header"""
        task = Mock()
        task.task_id = "task_001"
        task.status = "STAGED"
        task.description = "Test"

        blocks = SlackFormatter.format_task_list([task], status_filter="staged")

        assert "STAGED" in blocks[0]["text"]["text"]

    def test_task_list_status_emojis(self):
        """format_task_list uses correct status emojis"""
        statuses = [
            ("STAGED", "📝"),
            ("COMMITTED", "✔️"),
            ("RUNNING", "⏳"),
            ("COMPLETED", "✅"),
            ("FAILED", "❌")
        ]

        for status, emoji in statuses:
            task = Mock()
            task.task_id = "task_001"
            task.status = status
            task.description = "Test"

            blocks = SlackFormatter.format_task_list([task])
            task_block = blocks[1]  # After header

            assert emoji in task_block["text"]["text"]

    def test_task_list_truncates_at_10(self):
        """format_task_list limits to 10 tasks"""
        tasks = []
        for i in range(15):
            task = Mock()
            task.task_id = f"task_{i:03d}"
            task.status = "STAGED"
            task.description = f"Task {i}"
            tasks.append(task)

        blocks = SlackFormatter.format_task_list(tasks)

        # Should have header + 10 task blocks + context
        # Check context mentions showing 10 of 15
        context_blocks = [b for b in blocks if b.get("type") == "context"]
        assert len(context_blocks) > 0
        assert "10 of 15" in str(context_blocks)


class TestFormatErrorMessage:
    """Tests for format_error_message"""

    def test_basic_error_message(self):
        """format_error_message creates error block"""
        blocks = SlackFormatter.format_error_message("Something went wrong")

        assert len(blocks) == 1
        assert blocks[0]["type"] == "section"
        assert "Error" in blocks[0]["text"]["text"]
        assert "Something went wrong" in blocks[0]["text"]["text"]

    def test_long_error_truncated(self):
        """format_error_message truncates long errors"""
        long_error = "X" * 600

        blocks = SlackFormatter.format_error_message(long_error)

        assert len(blocks[0]["text"]["text"]) < 600
        assert "..." in blocks[0]["text"]["text"]


class TestFormatCompletionNotificationEdgeCases:
    """Edge case tests for format_completion_notification"""

    def test_long_description_truncated(self):
        """format_completion_notification truncates long descriptions"""
        summary = {
            "task_id": "task_001",
            "status": "success",
            "description": "X" * 600,  # Over 500 chars
            "execution_time": 30.0
        }

        blocks = SlackFormatter.format_completion_notification(summary)

        # Find description block
        desc_block = [b for b in blocks if "What you asked for" in str(b)][0]
        assert "..." in desc_block["text"]["text"]
        assert len(desc_block["text"]["text"]) < 600

    def test_result_path_parses_stream_json(self, tmp_path):
        """format_completion_notification parses stream-json output"""
        # Create a mock output file with stream-json content
        output_file = tmp_path / "task_001_output.json"
        stream_json = {
            "stdout": '\n'.join([
                '{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hello "}}',
                '{"type": "content_block_delta", "delta": {"type": "text_delta", "text": "World!"}}',
                '{"type": "other_event", "data": "ignored"}',
                'invalid json line'
            ]),
            "stderr": ""
        }
        output_file.write_text(json.dumps(stream_json))

        summary = {
            "task_id": "task_001",
            "status": "success",
            "description": "Test",
            "execution_time": 30.0,
            "result_path": str(output_file)
        }

        blocks = SlackFormatter.format_completion_notification(summary)

        # Should have parsed and included the response
        blocks_text = " ".join([str(b) for b in blocks])
        assert "Hello World!" in blocks_text

    def test_result_path_truncates_long_response(self, tmp_path):
        """format_completion_notification truncates long responses"""
        output_file = tmp_path / "task_001_output.json"
        long_text = "X" * 1500
        stream_json = {
            "stdout": f'{{"type": "content_block_delta", "delta": {{"type": "text_delta", "text": "{long_text}"}}}}',
            "stderr": ""
        }
        output_file.write_text(json.dumps(stream_json))

        summary = {
            "task_id": "task_001",
            "status": "success",
            "description": "Test",
            "execution_time": 30.0,
            "result_path": str(output_file)
        }

        blocks = SlackFormatter.format_completion_notification(summary)

        blocks_text = " ".join([str(b) for b in blocks])
        assert "truncated" in blocks_text.lower()

    def test_result_path_handles_invalid_json(self, tmp_path):
        """format_completion_notification handles invalid JSON gracefully"""
        output_file = tmp_path / "task_001_output.json"
        output_file.write_text("{ invalid json")

        summary = {
            "task_id": "task_001",
            "status": "success",
            "description": "Test",
            "execution_time": 30.0,
            "result_path": str(output_file)
        }

        # Should not raise
        blocks = SlackFormatter.format_completion_notification(summary)
        assert len(blocks) > 0

    def test_modified_files_truncated(self):
        """format_completion_notification truncates modified files list"""
        summary = {
            "task_id": "task_001",
            "status": "success",
            "description": "Test",
            "execution_time": 30.0,
            "file_changes": {
                "created": [],
                "modified": [f"file_{i}.py" for i in range(10)],
                "deleted": []
            }
        }

        blocks = SlackFormatter.format_completion_notification(summary)

        blocks_text = " ".join([str(b) for b in blocks])
        assert "Modified" in blocks_text
        assert "more" in blocks_text

    def test_deleted_files_truncated(self):
        """format_completion_notification truncates deleted files list"""
        summary = {
            "task_id": "task_001",
            "status": "success",
            "description": "Test",
            "execution_time": 30.0,
            "file_changes": {
                "created": [],
                "modified": [],
                "deleted": [f"file_{i}.py" for i in range(10)]
            }
        }

        blocks = SlackFormatter.format_completion_notification(summary)

        blocks_text = " ".join([str(b) for b in blocks])
        assert "Deleted" in blocks_text
        assert "more" in blocks_text

    def test_long_error_message_truncated(self):
        """format_completion_notification truncates long error messages"""
        summary = {
            "task_id": "task_001",
            "status": "failed",
            "description": "Test",
            "execution_time": 10.0,
            "error_message": "E" * 500  # Over 300 chars
        }

        blocks = SlackFormatter.format_completion_notification(summary)

        error_blocks = [b for b in blocks if "Error" in str(b)]
        assert len(error_blocks) > 0
        # Error should be truncated
        assert "..." in str(error_blocks[0])

    def test_result_path_shown_in_context(self):
        """format_completion_notification shows result path"""
        summary = {
            "task_id": "task_001",
            "status": "success",
            "description": "Test",
            "execution_time": 30.0,
            "result_path": "/path/to/output.json"
        }

        blocks = SlackFormatter.format_completion_notification(summary)

        context_blocks = [b for b in blocks if b.get("type") == "context"]
        assert len(context_blocks) > 0
        assert "/path/to/output.json" in str(context_blocks)


class TestFormatTaskListEdgeCases:
    """Edge case tests for format_task_list"""

    def test_long_task_description_truncated(self):
        """format_task_list truncates long task descriptions"""
        task = Mock()
        task.task_id = "task_001"
        task.status = "STAGED"
        task.description = "D" * 200  # Over 100 chars

        blocks = SlackFormatter.format_task_list([task])

        task_block = blocks[1]  # After header
        assert "..." in task_block["text"]["text"]
        assert len(task_block["text"]["text"]) < 200

    def test_unknown_status_uses_question_mark(self):
        """format_task_list uses ? for unknown status"""
        task = Mock()
        task.task_id = "task_001"
        task.status = "UNKNOWN_STATUS"
        task.description = "Test"

        blocks = SlackFormatter.format_task_list([task])

        task_block = blocks[1]
        assert "❓" in task_block["text"]["text"]

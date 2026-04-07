from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from openharness.monitor import _derive_flow_state, build_monitor_snapshot, build_summary_payload


def test_derive_flow_state_from_executing_log():
    state = _derive_flow_state(
        log_lines=["[2026-04-07 21:00:00] Executing: coder auth 5"],
        timeline_items=[],
        missing_info={"missing_items": []},
        test_report={},
        review_report={},
        feature_data=None,
    )
    assert state["overall_state"] == "running"
    assert state["active_stage"] == "Coder"
    assert state["current_task"] == "coder auth 5"


def test_derive_flow_state_paused_by_missing_info():
    state = _derive_flow_state(
        log_lines=[],
        timeline_items=[],
        missing_info={"missing_items": [{"desc": "需要人工补充数据库账号", "status": "pending"}]},
        test_report={},
        review_report={},
        feature_data=None,
    )
    assert state["overall_state"] == "paused"
    assert state["exception_message"] == "需要人工补充数据库账号"


def test_derive_flow_state_completed_from_logs():
    state = _derive_flow_state(
        log_lines=["[2026-04-07 21:00:00] PROJECT COMPLETE!"],
        timeline_items=[],
        missing_info={"missing_items": []},
        test_report={},
        review_report={},
        feature_data=None,
    )
    assert state["overall_state"] == "completed"
    assert state["active_stage"] == "Complete"


def test_derive_flow_state_stuck_from_logs():
    state = _derive_flow_state(
        log_lines=["[2026-04-07 21:00:00] No valid decision from orchestrator (3/3)"],
        timeline_items=[],
        missing_info={"missing_items": []},
        test_report={},
        review_report={},
        feature_data=None,
    )
    assert state["overall_state"] == "stuck"
    assert "Orchestrator" in state["exception_message"]


def test_summary_payload_contains_new_fields(tmp_path):
    summary = build_summary_payload(build_monitor_snapshot(str(tmp_path)))
    assert summary["overall_state"] == "idle"
    assert summary["active_stage"] == ""
    assert summary["current_task"] == ""
    assert summary["state_message"] == "尚未检测到运行中的 Harness 流程。"
    assert summary["exception_message"] == ""

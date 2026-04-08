from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from openharness.monitor import (  # noqa: E402
    _build_recent_cycles,
    _derive_flow_state,
    _derive_loop_view,
    build_monitor_snapshot,
    build_summary_payload,
)


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


def test_running_coder_loop_highlights_execute_leg():
    state = _derive_flow_state(
        log_lines=["[2026-04-07 21:00:00] Executing: coder auth 5"],
        timeline_items=[
            {
                "cycle": "4",
                "time": "2026-04-07 20:59:40",
                "agent": "coder",
                "args": "auth 5",
                "duration": "12.50s",
                "status": "started",
            }
        ],
        missing_info={"missing_items": []},
        test_report={},
        review_report={},
        feature_data=None,
    )
    recent_cycles = _build_recent_cycles(
        [
            {
                "cycle": "4",
                "time": "2026-04-07 20:59:40",
                "agent": "coder",
                "args": "auth 5",
                "duration": "12.50s",
                "status": "started",
            }
        ]
    )
    loop_view = _derive_loop_view(state, recent_cycles)
    assert loop_view["active_leg"] == "execute"
    assert recent_cycles[0]["agent"] == "coder"
    assert recent_cycles[0]["status_tone"] == "running"


def test_successful_cycle_shows_return_to_orchestrator():
    timeline_items = [
        {
            "cycle": "5",
            "time": "2026-04-07 21:05:00",
            "agent": "tester",
            "args": "auth",
            "duration": "18.00s",
            "status": "success",
        }
    ]
    state = _derive_flow_state(
        log_lines=[],
        timeline_items=timeline_items,
        missing_info={"missing_items": []},
        test_report={},
        review_report={},
        feature_data=None,
    )
    recent_cycles = _build_recent_cycles(timeline_items)
    loop_view = _derive_loop_view(state, recent_cycles)
    assert loop_view["active_leg"] in {"verify", "return"}
    assert "返回 Orchestrator" in state["state_message"]
    assert recent_cycles[0]["handoff_message"] == "本轮结束后回到 Orchestrator，等待下一轮调度。"


def test_derive_flow_state_paused_by_missing_info():
    state = _derive_flow_state(
        log_lines=[],
        timeline_items=[],
        missing_info={"missing_items": [{"desc": "需要人工补充数据库账号", "status": "pending"}]},
        test_report={},
        review_report={},
        feature_data=None,
    )
    loop_view = _derive_loop_view(state, [])
    assert state["overall_state"] == "paused"
    assert state["exception_message"] == "需要人工补充数据库账号"
    assert loop_view["active_leg"] == "return"
    assert loop_view["return_state"] == "blocked"


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
    loop_view = _derive_loop_view(state, [])
    assert state["overall_state"] == "stuck"
    assert "Orchestrator" in state["exception_message"]
    assert loop_view["active_leg"] == "return"
    assert loop_view["return_state"] == "failed"


def test_summary_payload_contains_loop_fields(tmp_path):
    summary = build_summary_payload(build_monitor_snapshot(str(tmp_path)))
    assert summary["overall_state"] == "idle"
    assert summary["active_stage"] == ""
    assert summary["current_task"] == ""
    assert summary["state_message"] == "尚未检测到运行中的 Harness 流程。"
    assert summary["exception_message"] == ""
    assert summary["loop_headline"] == "Loop 尚未启动"
    assert summary["loop_view"]["active_leg"] == "dispatch"
    assert summary["recent_cycles"] == []

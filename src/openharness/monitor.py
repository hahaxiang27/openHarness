"""Read-only local monitoring server for openHarness."""

from __future__ import annotations

import json
import os
import re
import threading
import webbrowser
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List
from urllib.parse import urlparse

try:
    from openharness.generator.changes import get_active_change, get_change_dir, parse_meta_file
    from openharness.runtime.context import CYCLE_LOG_FILENAME, LOG_FILENAME, RuntimeContext
    from openharness.runtime.state import get_features_from_data, get_progress, normalize_feature_list
    from openharness.utils.config import get_backend_from_config
    from openharness.utils.project_id import get_or_create_project_id
except ImportError:
    from generator.changes import get_active_change, get_change_dir, parse_meta_file
    from runtime.context import CYCLE_LOG_FILENAME, LOG_FILENAME, RuntimeContext
    from runtime.state import get_features_from_data, get_progress, normalize_feature_list
    from utils.config import get_backend_from_config
    from utils.project_id import get_or_create_project_id


TAIL_READ_BYTES = 65536
DEFAULT_LOG_LINES = 80
DEFAULT_TIMELINE_LIMIT = 12
DEFAULT_REFRESH_MS = 1500
STAGE_ORDER = ("Initializer", "Orchestrator", "Coder", "Tester", "Fixer", "Reviewer", "Complete")
STAGE_LABELS = {"Initializer": "初始化", "Orchestrator": "编排", "Coder": "编码", "Tester": "测试", "Fixer": "修复", "Reviewer": "审查", "Complete": "完成"}

HTML_PAGE = """<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>openHarness 流程监控</title><style>
:root{--bg:#f4f1e8;--panel:#fffbf5;--text:#1f1c17;--muted:#6e695d;--line:#d8ccb5;--accent:#b85c38;--ok:#2f6f62;--warn:#b88400;--danger:#9d2f2f}
*{box-sizing:border-box}body{margin:0;font-family:"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:var(--text);background:radial-gradient(circle at top right,rgba(184,92,56,.08),transparent 26%),radial-gradient(circle at left center,rgba(47,111,98,.08),transparent 30%),var(--bg)}
.shell{max-width:980px;margin:0 auto;padding:24px 14px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:18px}.panel+.panel{margin-top:14px}.title{margin:0 0 4px;font-size:28px;font-weight:800}.sub{margin:0 0 10px;color:var(--muted);font-size:13px;font-weight:700}.lead,.foot,.task{color:var(--muted);line-height:1.6}.eyebrow{margin:0 0 10px;font-size:12px;color:var(--muted);text-transform:uppercase;font-weight:800;letter-spacing:.04em}
.row,.steps,.meta{display:flex;flex-wrap:wrap;gap:10px}.chip,.step,.meta span{background:#fff;border:1px solid var(--line);border-radius:14px}.chip{min-width:120px;padding:11px 12px}.chip b{display:block;font-size:11px;color:var(--muted);margin-bottom:4px}.chip code{font-size:15px;font-weight:800;word-break:break-word}.state-running{background:rgba(184,92,56,.12);border-color:transparent;color:var(--accent)}.state-completed{background:rgba(47,111,98,.12);border-color:transparent;color:var(--ok)}.state-paused{background:rgba(184,132,0,.12);border-color:transparent;color:var(--warn)}.state-stuck{background:rgba(157,47,47,.12);border-color:transparent;color:var(--danger)}.state-idle{background:rgba(110,105,93,.1);border-color:transparent;color:var(--muted)}
.step{padding:11px 12px;min-width:124px;display:flex;gap:8px;align-items:center}.step i{display:inline-flex;width:22px;height:22px;border-radius:999px;align-items:center;justify-content:center;background:rgba(110,105,93,.1);font-style:normal;font-size:11px;font-weight:800;color:var(--muted)}.step strong{display:block;font-size:13px;font-family:Consolas,"Courier New",monospace}.step small{display:block;color:var(--muted);font-size:11px}.step.active{background:rgba(184,92,56,.12);border-color:rgba(184,92,56,.35)}.step.active i{background:rgba(184,92,56,.16);color:var(--accent)}.arrow{color:#b7aa92;font-weight:800;padding:0 2px}
.msg{margin:0;font-size:26px;line-height:1.35;font-weight:850}.meta span{padding:8px 10px;color:var(--muted);font-size:12px}.meta code{color:var(--text);font-family:Consolas,"Courier New",monospace;font-weight:700}.alert{background:rgba(157,47,47,.06);border-color:rgba(157,47,47,.18)}.alert h3{margin:0;color:var(--danger);font-size:14px}.hide{display:none}@media(max-width:720px){.title{font-size:24px}.msg{font-size:22px}.arrow{display:none}.step,.chip{min-width:calc(50% - 10px)}}@media(max-width:460px){.step,.chip{min-width:100%}}
</style></head><body><div class='shell'><h1 class='title'>openHarness 流程监控</h1><p class='sub'>openHarness Monitor · read-only</p><p class='lead'>首页只回答三件事：现在跑到哪一步、当前正在做什么、是否被阻塞。</p><section class='panel'><p class='eyebrow'>Overview</p><div class='row'><div class='chip' id='stateChip'><b>overall_state</b><code id='overallState'>-</code></div><div class='chip'><b>active_stage</b><code id='activeStage'>-</code></div><div class='chip'><b>backend</b><code id='backendValue'>-</code></div><div class='chip'><b>active_change</b><code id='activeChange'>-</code></div><div class='chip'><b>cycle</b><code id='cycleValue'>-</code></div></div></section><section class='panel'><p class='eyebrow'>Flow</p><div class='steps' id='steps'></div></section><section class='panel'><p class='eyebrow'>Current Action</p><h2 class='msg' id='stateMessage'>正在加载…</h2><p class='task' id='taskMessage'>-</p><div class='meta'><span>project_id: <code id='projectId'>-</code></span><span>current_agent: <code id='currentAgent'>-</code></span><span>progress: <code id='progressValue'>-</code></span></div></section><section class='panel alert hide' id='exceptionPanel'><p class='eyebrow'>Attention</p><h3>流程异常提示</h3><p class='task' id='exceptionMessage'></p></section><p class='foot' id='footerText'>上次刷新：-</p></div><script>
const stages=[["Initializer","初始化"],["Orchestrator","编排"],["Coder","编码"],["Tester","测试"],["Fixer","修复"],["Reviewer","审查"],["Complete","完成"]];
function esc(t){return String(t||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function label(v){return({running:"运行中",paused:"已暂停",completed:"已完成",stuck:"卡住",idle:"空闲"})[v]||v||"-"}
function renderSteps(active){const parts=[];stages.forEach((s,i)=>{parts.push(`<div class="step${s[0]===active?" active":""}"><i>${i+1}</i><span><strong>${esc(s[0])}</strong><small>${esc(s[1])}</small></span></div>`);if(i<stages.length-1)parts.push('<span class="arrow">→</span>')});document.getElementById("steps").innerHTML=parts.join("")}
async function load(){const s=await fetch("/api/monitor/summary").then(r=>r.json());document.getElementById("stateChip").className=`chip state-${s.overall_state||"idle"}`;document.getElementById("overallState").textContent=label(s.overall_state);document.getElementById("activeStage").textContent=s.active_stage?`${s.active_stage} · ${s.active_stage_zh||"-"}`:"-";document.getElementById("backendValue").textContent=s.backend||"-";document.getElementById("activeChange").textContent=s.active_change||"legacy-flat-input";document.getElementById("cycleValue").textContent=s.current_cycle||"-";document.getElementById("stateMessage").textContent=s.state_message||"暂无运行信息。";document.getElementById("taskMessage").textContent=s.current_task?`current_task: ${s.current_task}`:"当前没有可展示的任务参数。";document.getElementById("projectId").textContent=s.project_id||"-";document.getElementById("currentAgent").textContent=s.current_agent||"-";document.getElementById("progressValue").textContent=s.progress?`${s.progress.passing}/${s.progress.total} (${s.progress.percent}%)`:"-";document.getElementById("footerText").innerHTML=`上次刷新：${esc(s.last_update_time||"-")} · project_dir: <code>${esc(s.project_dir||"-")}</code>`;renderSteps(s.active_stage||"");const p=document.getElementById("exceptionPanel");if(s.exception_message){p.classList.remove("hide");document.getElementById("exceptionMessage").textContent=s.exception_message}else{p.classList.add("hide");document.getElementById("exceptionMessage").textContent=""}}
load();setInterval(load,""" + str(DEFAULT_REFRESH_MS) + """);
</script></body></html>"""


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _tail_lines(path: Path, limit: int = DEFAULT_LOG_LINES, max_bytes: int = TAIL_READ_BYTES) -> List[str]:
    if not path.exists():
        return []
    try:
        with path.open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            handle.seek(max(handle.tell() - max_bytes, 0))
            data = handle.read().decode("utf-8", errors="replace")
    except Exception:
        return []
    lines = [line.rstrip("\n") for line in data.splitlines() if line.strip()]
    return lines[-limit:]


def _parse_cycle_blocks(path: Path, limit: int = DEFAULT_TIMELINE_LIMIT) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    items: List[Dict[str, str]] = []
    for segment in re.split(r"\n=+\n", text):
        if "Cycle:" not in segment:
            continue
        item: Dict[str, str] = {}
        for line in segment.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key in {"cycle", "time", "agent", "args", "duration", "status"}:
                item[key] = value
        if item:
            items.append(item)
    return items[-limit:]


def _stage_from_agent(agent: str) -> str:
    return {
        "initializer": "Initializer",
        "orchestrator": "Orchestrator",
        "coder": "Coder",
        "tester": "Tester",
        "fixer": "Fixer",
        "reviewer": "Reviewer",
        "complete": "Complete",
    }.get((agent or "").strip().lower(), "")


def _format_task(agent: str, args: str) -> str:
    return " ".join(part for part in [(agent or "").strip(), (args or "").strip()] if part).strip()


def _extract_latest_execution(log_lines: List[str]) -> Dict[str, str]:
    pattern = re.compile(r"Executing:\s*(\w+)(?:\s+(.*))?$", re.IGNORECASE)
    for line in reversed(log_lines):
        match = pattern.search(line)
        if match:
            return {"agent": match.group(1).strip().lower(), "args": (match.group(2) or "").strip()}
    return {}


def _get_pending_blockers(missing_info) -> List[Dict[str, object]]:
    if not isinstance(missing_info, dict):
        return []
    return [
        item
        for item in missing_info.get("missing_items", [])
        if isinstance(item, dict) and item.get("status", "pending") == "pending"
    ]


def _has_stuck_signal(log_lines: List[str]) -> bool:
    for line in log_lines[-20:]:
        if "STUCK" in line.upper():
            return True
        match = re.search(r"No valid decision from orchestrator \((\d+)/(\d+)\)", line, re.IGNORECASE)
        if match and match.group(1) == match.group(2):
            return True
    return False


def _running_message(stage: str, current_task: str) -> str:
    if stage == "Orchestrator":
        return "Orchestrator 正在读取状态并决定下一步。"
    if stage == "Initializer":
        return "Initializer 正在初始化项目状态。"
    if stage and current_task:
        return f"{stage} 正在执行 {current_task}。"
    if stage:
        return f"{stage} 正在运行。"
    return "Harness 正在运行。"


def _cycle_message(stage: str, current_task: str, latest_status: str) -> str:
    status = (latest_status or "").strip().lower()
    if status in {"started", "running"}:
        return _running_message(stage, current_task)
    if status in {"success", "done", "pass"} and stage:
        return f"{stage} 刚完成最近一步，等待下一次调度。"
    if stage and current_task:
        return f"最近一次执行是 {current_task}。"
    if stage:
        return f"最近一次执行阶段为 {stage}。"
    return "Harness 已有运行记录。"


def _derive_flow_state(
    log_lines: List[str],
    timeline_items: List[Dict[str, str]],
    missing_info,
    test_report,
    review_report,
    feature_data,
) -> Dict[str, str]:
    pending_blockers = _get_pending_blockers(missing_info)
    latest_cycle = timeline_items[-1] if timeline_items else {}
    latest_status = latest_cycle.get("status", "")
    latest_execution = _extract_latest_execution(log_lines)
    overall_state = "running"
    active_stage = ""
    current_agent = ""
    current_task = ""
    state_message = ""
    exception_message = ""

    if any("PROJECT COMPLETE" in line.upper() for line in log_lines[-20:]):
        overall_state = "completed"
        active_stage = "Complete"
        current_agent = "complete"
        state_message = "Harness 已完成当前变更，流程结束。"
    elif pending_blockers or any("ORCHESTRATOR PAUSED" in line.upper() for line in log_lines[-20:]):
        overall_state = "paused"
        active_stage = "Orchestrator"
        current_agent = "pause_for_human"
        state_message = "Harness 已暂停，等待人工处理。"
        if pending_blockers:
            blocker = pending_blockers[0]
            exception_message = str(blocker.get("desc") or blocker.get("description") or "").strip()
        if not exception_message:
            exception_message = "检测到待处理阻塞项，请检查 .openharness/missing_info.json。"
    elif _has_stuck_signal(log_lines):
        overall_state = "stuck"
        active_stage = "Orchestrator"
        current_agent = "stuck"
        state_message = "Harness 当前无法继续推进。"
        exception_message = "Orchestrator 未能给出有效决策，请检查运行状态或重置流程。"
    elif latest_execution:
        current_agent = latest_execution["agent"]
        active_stage = _stage_from_agent(current_agent)
        current_task = _format_task(current_agent, latest_execution["args"])
        state_message = _running_message(active_stage, current_task)
    elif any("Calling orchestrator" in line for line in log_lines[-10:]):
        current_agent = "orchestrator"
        active_stage = "Orchestrator"
        state_message = "Orchestrator 正在读取状态并决定下一步。"
    elif latest_cycle:
        current_agent = latest_cycle.get("agent", "").strip().lower()
        active_stage = _stage_from_agent(current_agent)
        current_task = _format_task(current_agent, latest_cycle.get("args", ""))
        state_message = _cycle_message(active_stage, current_task, latest_status)
    elif feature_data:
        current_agent = "orchestrator"
        active_stage = "Orchestrator"
        state_message = "Harness 已就绪，等待 Orchestrator 决定下一步。"
    else:
        overall_state = "idle"
        state_message = "尚未检测到运行中的 Harness 流程。"

    if overall_state == "running":
        test_overall = test_report.get("overall", "unknown") if isinstance(test_report, dict) else "unknown"
        review_overall = review_report.get("overall", "unknown") if isinstance(review_report, dict) else "unknown"
        lower_status = latest_status.lower()
        if "fail" in lower_status or "error" in lower_status:
            exception_message = f"最近一次执行状态为 {latest_status}，流程可能会进入修复阶段。"
        elif test_overall == "fail":
            exception_message = "测试报告显示失败，流程应进入 Fixer 或 Coder。"
        elif review_overall == "fail":
            exception_message = "审查报告显示失败，流程应进入 Fixer。"

    if not current_task and latest_cycle and overall_state == "running":
        current_task = _format_task(latest_cycle.get("agent", "").strip().lower(), latest_cycle.get("args", ""))

    current_phase = active_stage or {"completed": "Completed", "paused": "Paused", "stuck": "Stuck", "idle": "Idle"}.get(overall_state, "Running")
    return {
        "overall_state": overall_state,
        "active_stage": active_stage,
        "current_phase": current_phase,
        "current_agent": current_agent,
        "current_task": current_task,
        "state_message": state_message,
        "exception_message": exception_message,
        "latest_status": latest_status,
    }


def build_summary_payload(snapshot: Dict[str, object]) -> Dict[str, object]:
    return {key: value for key, value in snapshot.items() if key not in ("timeline", "logs", "blockers", "features")}


def build_monitor_snapshot(project_dir: str) -> Dict[str, object]:
    runtime = RuntimeContext(project_dir=project_dir)
    project_path = Path(project_dir).resolve()
    log_path = project_path / LOG_FILENAME
    cycle_log_path = Path(runtime.paths.openharness_dir) / CYCLE_LOG_FILENAME
    feature_list_path = Path(runtime.paths.feature_list_file)
    test_report_path = Path(runtime.paths.test_report_file)
    review_report_path = Path(runtime.paths.review_report_file)
    missing_info_path = Path(runtime.paths.missing_info_file)

    log_lines = _tail_lines(log_path)
    timeline_items = _parse_cycle_blocks(cycle_log_path)
    feature_data = normalize_feature_list(_load_json(feature_list_path, None))
    test_report = _load_json(test_report_path, {})
    review_report = _load_json(review_report_path, {})
    missing_info = _load_json(missing_info_path, {"missing_items": []})
    active_change = get_active_change(project_dir)
    flow_state = _derive_flow_state(log_lines, timeline_items, missing_info, test_report, review_report, feature_data)
    progress = get_progress(feature_data) if feature_data else None
    blockers = missing_info.get("missing_items", []) if isinstance(missing_info, dict) else []
    pending_blockers = _get_pending_blockers(missing_info)
    current_cycle = timeline_items[-1]["cycle"] if timeline_items else ""
    active_change_title = ""
    if active_change:
        change_dir = get_change_dir(project_dir, active_change)
        if change_dir.exists():
            active_change_title = parse_meta_file(change_dir).title

    return {
        "project_dir": str(project_path),
        "project_id": get_or_create_project_id(project_dir),
        "backend": get_backend_from_config(project_dir),
        "active_change": active_change,
        "active_change_title": active_change_title,
        "current_phase": flow_state["current_phase"],
        "current_agent": flow_state["current_agent"],
        "current_cycle": current_cycle,
        "latest_status": flow_state["latest_status"],
        "last_update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "progress": progress,
        "overall_test_status": test_report.get("overall", "unknown") if isinstance(test_report, dict) else "unknown",
        "overall_review_status": review_report.get("overall", "unknown") if isinstance(review_report, dict) else "unknown",
        "pending_blockers": len(pending_blockers),
        "overall_state": flow_state["overall_state"],
        "active_stage": flow_state["active_stage"],
        "active_stage_zh": STAGE_LABELS.get(flow_state["active_stage"], ""),
        "current_task": flow_state["current_task"],
        "state_message": flow_state["state_message"],
        "exception_message": flow_state["exception_message"],
        "timeline": {"items": timeline_items},
        "logs": {"items": log_lines},
        "blockers": {"items": blockers},
        "features": {"items": get_features_from_data(feature_data) if feature_data else []},
    }


class MonitorRequestHandler(BaseHTTPRequestHandler):
    """Serve the monitor HTML shell and read-only JSON endpoints."""

    project_dir = "."

    def _write_json(self, payload: Dict[str, object], status: int = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_html(self, body: str, status: int = HTTPStatus.OK) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format, *args):  # noqa: A003
        return

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._write_html(HTML_PAGE)
            return

        snapshot = build_monitor_snapshot(self.project_dir)
        if parsed.path == "/api/monitor/summary":
            self._write_json(build_summary_payload(snapshot))
            return
        if parsed.path == "/api/monitor/timeline":
            self._write_json(snapshot["timeline"])
            return
        if parsed.path == "/api/monitor/logs":
            self._write_json(snapshot["logs"])
            return
        if parsed.path == "/api/monitor/blockers":
            self._write_json(snapshot["blockers"])
            return
        if parsed.path == "/api/monitor/features":
            self._write_json(snapshot["features"])
            return
        self._write_json({"error": "not found"}, status=HTTPStatus.NOT_FOUND)


def serve_monitor(project_dir: str = ".", host: str = "127.0.0.1", port: int = 8765, open_browser: bool = False):
    """Start a local read-only monitor server."""
    handler_cls = type("ProjectMonitorHandler", (MonitorRequestHandler,), {"project_dir": project_dir})
    server = ThreadingHTTPServer((host, port), handler_cls)
    url = f"http://{host}:{port}"
    print(f"[openHarness] Monitor running at {url}")
    print(f"[openHarness] Project: {Path(project_dir).resolve()}")
    if open_browser:
        threading.Timer(0.3, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[openHarness] Monitor stopped.")
    finally:
        server.server_close()

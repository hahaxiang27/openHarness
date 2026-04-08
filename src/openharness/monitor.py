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
DEFAULT_RECENT_CYCLES = 6
DEFAULT_REFRESH_MS = 1500
STAGE_ORDER = ("Initializer", "Orchestrator", "Coder", "Tester", "Fixer", "Reviewer", "Complete")
STAGE_LABELS = {
    "Initializer": "初始化",
    "Orchestrator": "调度",
    "Coder": "编码",
    "Tester": "测试",
    "Fixer": "修复",
    "Reviewer": "审查",
    "Complete": "完成",
}

HTML_PAGE = """<!doctype html>
<html lang='zh-CN'>
<head>
<meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'>
<title>openHarness 流程监控</title>
<style>
:root{--bg:#0f1419;--panel:#171d24;--panel-strong:#1c2530;--line:#2e3b48;--line-strong:#536577;--text:#edf2f7;--muted:#8fa0b2;--accent:#ff9a3c;--accent-soft:rgba(255,154,60,.16);--ok:#51d0a5;--ok-soft:rgba(81,208,165,.16);--warn:#ffd166;--warn-soft:rgba(255,209,102,.16);--danger:#ff6b6b;--danger-soft:rgba(255,107,107,.16);--shadow:0 18px 54px rgba(0,0,0,.34)}
*{box-sizing:border-box}html,body{margin:0}body{min-height:100vh;font-family:"Bahnschrift","Segoe UI","PingFang SC","Microsoft YaHei",sans-serif;color:var(--text);background:radial-gradient(circle at 20% 0%,rgba(81,208,165,.11),transparent 28%),radial-gradient(circle at 100% 20%,rgba(255,154,60,.12),transparent 32%),linear-gradient(180deg,#0c1116 0%,#0f1419 55%,#111920 100%)}.shell{max-width:1160px;margin:0 auto;padding:28px 18px 34px}.mast{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;margin-bottom:16px}.title{margin:0;font-size:clamp(2rem,4vw,3.4rem);line-height:1;font-weight:850;letter-spacing:.02em;text-transform:uppercase}.sub{margin:6px 0 0;color:var(--muted);font-size:12px;font-weight:700;letter-spacing:.18em;text-transform:uppercase}.lead{max-width:620px;margin:0;color:var(--muted);line-height:1.6}
.panel{background:linear-gradient(180deg,rgba(255,255,255,.02),rgba(255,255,255,0)),var(--panel);border:1px solid var(--line);border-radius:24px;box-shadow:var(--shadow)}.panel+.panel{margin-top:16px}.hero{padding:24px}.eyebrow{margin:0 0 12px;color:var(--muted);font-size:11px;font-weight:800;letter-spacing:.18em;text-transform:uppercase}.heroGrid{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(280px,.95fr);gap:18px}.headline{margin:0;font-size:clamp(1.6rem,3vw,2.8rem);line-height:1.08;font-weight:850;max-width:12ch}.support{margin:10px 0 0;color:var(--muted);line-height:1.7;max-width:58ch}
.loopRail{margin-top:24px;padding:48px 24px 32px;border-radius:16px;border:2px solid rgba(143,160,178,.15);background:rgba(143,160,178,.03);position:relative;display:flex;justify-content:center}.loopRail::before{content:"CYCLE LOOP";position:absolute;top:16px;left:20px;font-size:12px;font-weight:850;letter-spacing:.15em;color:var(--muted)}.loopNodes{display:flex;flex-direction:column;align-items:center;gap:32px;width:100%;max-width:340px;position:relative}.loopNodes::before{content:"";position:absolute;top:0;bottom:0;left:50%;width:2px;background:var(--line-strong);transform:translateX(-50%);z-index:1}.loopNodes::after{content:"↺ NEXT CYCLE";position:absolute;top:32px;bottom:32px;left:-44px;width:44px;border-left:2px dashed var(--line-strong);border-top:2px dashed var(--line-strong);border-bottom:2px dashed var(--line-strong);border-radius:12px 0 0 12px;z-index:1;writing-mode:vertical-rl;text-orientation:mixed;transform:rotate(180deg);text-align:center;color:var(--muted);font-size:11px;font-weight:800;letter-spacing:.1em;padding-right:6px;display:flex;align-items:center;justify-content:center}.node{position:relative;z-index:2;width:100%;padding:16px 20px;border-radius:10px;border:2px solid transparent;text-align:center;box-shadow:0 6px 16px rgba(0,0,0,.2);transition:all .3s ease}.node:nth-child(1){background:linear-gradient(135deg,#1f2f45,#15202e);border-color:#344f73}.node:nth-child(2){background:linear-gradient(135deg,#42242c,#2e191f);border-color:#633642}.node:nth-child(3){background:linear-gradient(135deg,#1e362b,#15261e);border-color:#2a4d3d}.node:nth-child(4){background:linear-gradient(135deg,#3d341a,#2a2412);border-color:#5e5027}.node::after{content:"▼";position:absolute;bottom:-24px;left:50%;transform:translateX(-50%);color:var(--line-strong);font-size:13px;background:rgba(21,28,34,.95);padding:0 2px}.node:last-child::after{display:none}.nodeMark{display:none}.nodeLabel{display:block;font-size:15px;font-weight:850;letter-spacing:.08em;text-transform:uppercase;color:#fff}.nodeDesc{display:block;margin-top:6px;color:rgba(255,255,255,.7);font-size:12px;line-height:1.5}.node.active,.node.return-alert{border-color:var(--accent);box-shadow:0 0 0 2px rgba(255,154,60,.4),0 8px 24px rgba(255,154,60,.2)}.node.active .nodeLabel,.node.return-alert .nodeLabel{color:var(--accent)}.node.active::after{color:var(--accent)}.node.verify,.node.complete{border-color:var(--ok);box-shadow:0 0 0 2px rgba(81,208,165,.4)}.node.verify .nodeLabel,.node.complete .nodeLabel{color:var(--ok)}.node.verify::after,.node.complete::after{color:var(--ok)}.node.muted{opacity:.52}
.heroMeta{display:grid;gap:12px;align-content:start}.statusCard,.detailCard,.metricStrip{padding:16px 18px;border-radius:20px;border:1px solid var(--line);background:#141a20}.stateBadge{display:inline-flex;align-items:center;gap:8px;padding:8px 12px;border-radius:999px;border:1px solid transparent;font-size:12px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.state-running{background:var(--accent-soft);color:var(--accent)}.state-completed{background:var(--ok-soft);color:var(--ok)}.state-paused{background:var(--warn-soft);color:var(--warn)}.state-stuck{background:var(--danger-soft);color:var(--danger)}.state-idle{background:rgba(143,160,178,.12);color:var(--muted)}.statusLine{margin:14px 0 0;font-size:14px;line-height:1.6;color:var(--muted)}.detailCard h3{margin:0;font-size:14px;text-transform:uppercase;letter-spacing:.12em;color:var(--muted)}.detailCard p{margin:10px 0 0;color:var(--text);line-height:1.6}.detailMeta{margin-top:12px;display:grid;gap:8px}.detailMeta span{color:var(--muted);font-size:12px}.detailMeta code{color:var(--text);font-weight:700;font-family:Consolas,"Courier New",monospace}
.metricStrip{padding:14px}.metricGrid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px}.metric{min-height:92px;border:1px solid var(--line);border-radius:16px;padding:12px;background:var(--panel-strong)}.metric b{display:block;font-size:11px;color:var(--muted);letter-spacing:.08em;text-transform:uppercase}.metric code,.metric span{display:block;margin-top:8px;font-size:16px;font-weight:850;color:var(--text);word-break:break-word;font-family:Consolas,"Courier New",monospace}.metric .progressText{font-family:inherit}
.cycles{padding:22px}.sectionHead{display:flex;align-items:end;justify-content:space-between;gap:12px;margin-bottom:14px}.sectionHead h2{margin:0;font-size:22px;text-transform:uppercase;letter-spacing:.04em}.sectionHead p{margin:0;color:var(--muted);line-height:1.6}.cycleList{display:grid;gap:12px}.cycleCard{border:1px solid var(--line);border-radius:18px;background:#141a20;padding:16px}.cycleTop{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.cycleId{display:flex;align-items:center;gap:10px}.cycleId strong{font-size:22px;line-height:1}.cycleId span{display:block;color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.1em}.tone{display:inline-flex;align-items:center;padding:7px 10px;border-radius:999px;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}.tone-running{background:var(--accent-soft);color:var(--accent)}.tone-success{background:var(--ok-soft);color:var(--ok)}.tone-failed{background:var(--danger-soft);color:var(--danger)}.tone-waiting{background:rgba(143,160,178,.12);color:var(--muted)}.cycleBody{margin-top:14px;display:grid;grid-template-columns:minmax(0,1.25fr) minmax(240px,.9fr);gap:16px}.taskTitle{margin:0;font-size:16px;font-weight:800}.taskArgs{margin:8px 0 0;color:var(--muted);line-height:1.6}.handoff{margin-top:14px;padding-top:12px;border-top:1px solid var(--line);color:var(--text);font-size:13px;line-height:1.6}.cycleMeta{display:grid;gap:10px}.metaItem{border:1px solid var(--line);border-radius:14px;padding:10px 12px;background:var(--panel-strong)}.metaItem b{display:block;color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.08em}.metaItem span{display:block;margin-top:6px;color:var(--text);font-size:13px;font-weight:700;font-family:Consolas,"Courier New",monospace;word-break:break-word}.empty{border:1px dashed var(--line-strong);border-radius:18px;padding:24px;color:var(--muted);background:rgba(255,255,255,.02)}
.alert{padding:18px 20px;border-radius:20px;border:1px solid rgba(255,107,107,.24);background:linear-gradient(180deg,rgba(255,107,107,.08),rgba(255,107,107,.03))}.alert h3{margin:0;font-size:14px;text-transform:uppercase;letter-spacing:.12em;color:var(--danger)}.alert p{margin:10px 0 0;line-height:1.7}.hide{display:none}.foot{margin:14px 2px 0;color:var(--muted);font-size:12px;line-height:1.6}.foot code{font-family:Consolas,"Courier New",monospace;color:var(--text)}
@media(max-width:980px){.heroGrid,.cycleBody,.metricGrid{grid-template-columns:1fr}}@media(max-width:640px){.shell{padding:18px 12px 26px}.mast{display:block}.lead{margin-top:14px}.hero,.cycles{padding:18px}.node{min-height:auto}.loopNodes::after{display:none}}
</style>
</head>
<body>
<div class='shell'>
  <div class='mast'>
    <div>
      <h1 class='title'>Harness Loop</h1>
      <p class='sub'>openHarness Monitor · read-only</p>
    </div>
    <p class='lead'>首页直接展示闭环过程：调度器发任务，agent 处理小任务，结果进入测试或校验，再回到调度器继续下一轮。</p>
  </div>
  <section class='panel hero'>
    <p class='eyebrow'>Harness Loop</p>
    <div class='heroGrid'>
      <div>
        <h2 class='headline' id='loopHeadline'>正在读取 loop 状态…</h2>
        <p class='support' id='loopSubheadline'>monitor 会用当前 agent、最近 cycle 和异常状态，展示这一轮如何回到 Orchestrator。</p>
        <div class='loopRail'><div class='loopNodes' id='loopNodes'></div></div>
      </div>
      <div class='heroMeta'>
        <div class='statusCard'>
          <span class='stateBadge state-idle' id='stateBadge'>idle</span>
          <p class='statusLine' id='stateMessage'>尚未检测到运行中的 Harness 流程。</p>
        </div>
        <div class='detailCard'>
          <h3>Current Action</h3>
          <p id='taskMessage'>当前没有可展示的任务参数。</p>
          <div class='detailMeta'>
            <span>project_id: <code id='projectId'>-</code></span>
            <span>current_agent: <code id='currentAgent'>-</code></span>
            <span>active_stage: <code id='activeStage'>-</code></span>
          </div>
        </div>
      </div>
    </div>
  </section>
  <section class='panel metricStrip'>
    <p class='eyebrow'>Overview</p>
    <div class='metricGrid'>
      <div class='metric'><b>overall_state</b><span id='overallState'>-</span></div>
      <div class='metric'><b>active_change</b><code id='activeChange'>-</code></div>
      <div class='metric'><b>backend</b><code id='backendValue'>-</code></div>
      <div class='metric'><b>cycle</b><code id='cycleValue'>-</code></div>
      <div class='metric'><b>progress</b><span class='progressText' id='progressValue'>-</span></div>
    </div>
  </section>
  <section class='panel cycles'>
    <div class='sectionHead'>
      <div>
        <h2>Recent Cycles</h2>
        <p>默认展示最近 6 轮，让 monitor 首页直接体现 harness 的循环特征。</p>
      </div>
    </div>
    <div class='cycleList' id='cycleList'></div>
  </section>
  <section class='alert hide' id='exceptionPanel'>
    <h3>为什么没有进入下一轮</h3>
    <p id='exceptionMessage'></p>
  </section>
  <p class='foot' id='footerText'>上次刷新：-</p>
</div>
<script>
const loopNodes=[{id:"dispatch",label:"Dispatch",desc:"Orchestrator 读取状态并决定下一项小任务。"},{id:"execute",label:"Execute",desc:"当前 agent 正在处理这一轮拆分出的任务。"},{id:"verify",label:"Verify",desc:"结果进入测试、审查或校验语义，确认本轮是否过关。"},{id:"return",label:"Return",desc:"本轮结果回到调度器，再决定下一轮执行方向。"}];
function esc(text){return String(text||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
function stateLabel(value){return({running:"运行中",paused:"已暂停",completed:"已完成",stuck:"卡住",idle:"空闲"})[value]||value||"-"}
function toneLabel(value){return({running:"进行中",success:"已回调度",failed:"失败",waiting:"等待中"})[value]||"等待中"}
function statusLabel(value){const normalized=String(value||"").toLowerCase();if(["started","running"].includes(normalized))return"running";if(["success","done","pass"].includes(normalized))return"success";if(normalized.includes("fail")||normalized.includes("error"))return"failed";return"waiting"}
function renderLoop(loopView){const activeLeg=loopView&&loopView.active_leg?loopView.active_leg:"dispatch";const overallState=loopView&&loopView.overall_state?loopView.overall_state:"idle";const returnState=loopView&&loopView.return_state?loopView.return_state:"waiting";document.getElementById("loopNodes").innerHTML=loopNodes.map((node,index)=>{let cls="node";if(overallState==="completed"){cls+=" complete"}else if(node.id===activeLeg){cls+=activeLeg==="verify"?" verify":" active";if(node.id==="return"&&(returnState==="blocked"||returnState==="failed"))cls+=" return-alert"}else if(overallState==="idle"&&index>0){cls+=" muted"}return`<div class="${cls}"><span class="nodeMark">${index+1}</span><span class="nodeLabel">${esc(node.label)}</span><span class="nodeDesc">${esc(node.desc)}</span></div>`}).join("")}
function renderCycles(items){const root=document.getElementById("cycleList");if(!items||!items.length){root.innerHTML=`<div class="empty">还没有 cycle 历史。启动 harness 后，这里会按轮次显示“执行 -> 测试/校验 -> 回调度器”的闭环记录。</div>`;return}root.innerHTML=items.map((item)=>{const tone=item.status_tone||statusLabel(item.status);const stage=item.stage?`${item.stage}${item.stage_zh?` · ${item.stage_zh}`:""}`:"-";const args=item.args||"当前轮次没有额外参数。";return`<article class="cycleCard"><div class="cycleTop"><div class="cycleId"><div><span>Cycle</span><strong>${esc(item.cycle||"-")}</strong></div><div><span>Agent</span><strong>${esc(item.agent||"-")}</strong></div></div><span class="tone tone-${esc(tone)}">${esc(toneLabel(tone))}</span></div><div class="cycleBody"><div><p class="taskTitle">${esc(stage)}</p><p class="taskArgs">${esc(args)}</p><div class="handoff">${esc(item.handoff_message||"本轮结束后将由 Orchestrator 决定下一步。")}</div></div><div class="cycleMeta"><div class="metaItem"><b>time</b><span>${esc(item.time||"-")}</span></div><div class="metaItem"><b>status</b><span>${esc(item.status||"-")}</span></div><div class="metaItem"><b>duration</b><span>${esc(item.duration||"-")}</span></div></div></div></article>`}).join("")}
async function load(){const summary=await fetch("/api/monitor/summary").then((response)=>response.json());const badge=document.getElementById("stateBadge");badge.className=`stateBadge state-${summary.overall_state||"idle"}`;badge.textContent=stateLabel(summary.overall_state);document.getElementById("loopHeadline").textContent=summary.loop_headline||"正在读取 loop 状态…";document.getElementById("loopSubheadline").textContent=summary.loop_subheadline||"暂无额外说明。";document.getElementById("stateMessage").textContent=summary.state_message||"暂无运行信息。";document.getElementById("taskMessage").textContent=summary.current_task?`current_task: ${summary.current_task}`:"当前没有可展示的任务参数。";document.getElementById("projectId").textContent=summary.project_id||"-";document.getElementById("currentAgent").textContent=summary.current_agent||"-";document.getElementById("activeStage").textContent=summary.active_stage?`${summary.active_stage}${summary.active_stage_zh?` · ${summary.active_stage_zh}`:""}`:"-";document.getElementById("overallState").textContent=stateLabel(summary.overall_state);document.getElementById("activeChange").textContent=summary.active_change||"legacy-flat-input";document.getElementById("backendValue").textContent=summary.backend||"-";document.getElementById("cycleValue").textContent=summary.current_cycle||"-";document.getElementById("progressValue").textContent=summary.progress?`${summary.progress.passing}/${summary.progress.total} (${summary.progress.percent}%)`:"-";document.getElementById("footerText").innerHTML=`上次刷新：${esc(summary.last_update_time||"-")} · project_dir: <code>${esc(summary.project_dir||"-")}</code>`;renderLoop(summary.loop_view||{});renderCycles(summary.recent_cycles||[]);const panel=document.getElementById("exceptionPanel");if(summary.exception_message){panel.classList.remove("hide");document.getElementById("exceptionMessage").textContent=summary.exception_message}else{panel.classList.add("hide");document.getElementById("exceptionMessage").textContent=""}}
load();setInterval(load,__REFRESH_MS__);
</script>
</body>
</html>
""".replace("__REFRESH_MS__", str(DEFAULT_REFRESH_MS))


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
        return "Initializer 正在准备项目状态，等待第一轮调度。"
    if stage and current_task:
        return f"{stage} 正在处理本轮任务：{current_task}。"
    if stage:
        return f"{stage} 正在执行当前轮次。"
    return "Harness 正在运行。"


def _cycle_message(stage: str, current_task: str, latest_status: str) -> str:
    status = (latest_status or "").strip().lower()
    if status in {"started", "running"}:
        return _running_message(stage, current_task)
    if status in {"success", "done", "pass"} and stage:
        return f"{stage} 已完成本轮，结果正返回 Orchestrator。"
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
        state_message = "Harness 已完成当前 change，闭环结束。"
    elif pending_blockers or any("ORCHESTRATOR PAUSED" in line.upper() for line in log_lines[-20:]):
        overall_state = "paused"
        active_stage = "Orchestrator"
        current_agent = "pause_for_human"
        state_message = "闭环停在调度器，等待人工处理后继续。"
        if pending_blockers:
            blocker = pending_blockers[0]
            exception_message = str(blocker.get("desc") or blocker.get("description") or "").strip()
        if not exception_message:
            exception_message = "检测到待处理阻塞项，请检查 .openharness/missing_info.json。"
    elif _has_stuck_signal(log_lines):
        overall_state = "stuck"
        active_stage = "Orchestrator"
        current_agent = "stuck"
        state_message = "闭环没有成功回到可继续调度的状态。"
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
            exception_message = f"最近一次执行状态为 {latest_status}，下一步通常会进入修复或重新调度。"
        elif test_overall == "fail":
            exception_message = "测试报告显示失败，流程应进入 Fixer 或回到 Coder。"
        elif review_overall == "fail":
            exception_message = "审查报告显示失败，流程应进入 Fixer。"

    if not current_task and latest_cycle and overall_state == "running":
        current_task = _format_task(latest_cycle.get("agent", "").strip().lower(), latest_cycle.get("args", ""))

    current_phase = active_stage or {
        "completed": "Completed",
        "paused": "Paused",
        "stuck": "Stuck",
        "idle": "Idle",
    }.get(overall_state, "Running")
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


def _status_tone(status: str) -> str:
    normalized = (status or "").strip().lower()
    if normalized in {"started", "running"}:
        return "running"
    if normalized in {"success", "done", "pass"}:
        return "success"
    if "fail" in normalized or "error" in normalized:
        return "failed"
    return "waiting"


def _handoff_message(agent: str, status: str) -> str:
    tone = _status_tone(status)
    if tone == "running":
        return f"{agent or '当前 agent'} 仍在执行，本轮尚未回到 Orchestrator。"
    if tone == "success":
        return "本轮结束后回到 Orchestrator，等待下一轮调度。"
    if tone == "failed":
        return "本轮失败，下一步通常进入 Fixer 或重新调度。"
    return "本轮结束后将由 Orchestrator 决定下一步。"


def _build_recent_cycles(timeline_items: List[Dict[str, str]], limit: int = DEFAULT_RECENT_CYCLES) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for item in reversed(timeline_items[-limit:]):
        agent = item.get("agent", "").strip().lower()
        stage = _stage_from_agent(agent)
        status = item.get("status", "")
        items.append(
            {
                "cycle": item.get("cycle", ""),
                "time": item.get("time", ""),
                "agent": agent,
                "stage": stage,
                "stage_zh": STAGE_LABELS.get(stage, ""),
                "args": item.get("args", ""),
                "status": status,
                "status_tone": _status_tone(status),
                "duration": item.get("duration", ""),
                "handoff_message": _handoff_message(agent, status),
            }
        )
    return items


def _derive_loop_view(flow_state: Dict[str, str], recent_cycles: List[Dict[str, str]]) -> Dict[str, str]:
    overall_state = flow_state["overall_state"]
    current_agent = (flow_state["current_agent"] or "").strip().lower()
    latest_cycle = recent_cycles[0] if recent_cycles else {}
    latest_tone = latest_cycle.get("status_tone", "waiting")

    if overall_state == "completed":
        return {
            "active_leg": "return",
            "active_agent": current_agent or "complete",
            "return_state": "closed",
            "overall_state": overall_state,
        }
    if overall_state == "paused":
        return {
            "active_leg": "return",
            "active_agent": current_agent or "orchestrator",
            "return_state": "blocked",
            "overall_state": overall_state,
        }
    if overall_state == "stuck":
        return {
            "active_leg": "return",
            "active_agent": current_agent or "orchestrator",
            "return_state": "failed",
            "overall_state": overall_state,
        }
    if overall_state == "idle":
        return {
            "active_leg": "dispatch",
            "active_agent": "",
            "return_state": "waiting",
            "overall_state": overall_state,
        }
    if current_agent == "orchestrator":
        return {
            "active_leg": "dispatch",
            "active_agent": current_agent,
            "return_state": latest_tone,
            "overall_state": overall_state,
        }
    if current_agent in {"tester", "reviewer"}:
        return {
            "active_leg": "verify",
            "active_agent": current_agent,
            "return_state": latest_tone,
            "overall_state": overall_state,
        }
    if latest_tone in {"success", "failed"} and not current_agent:
        return {
            "active_leg": "return",
            "active_agent": latest_cycle.get("agent", ""),
            "return_state": latest_tone,
            "overall_state": overall_state,
        }
    return {
        "active_leg": "execute",
        "active_agent": current_agent,
        "return_state": latest_tone,
        "overall_state": overall_state,
    }


def _loop_headline_and_subheadline(
    flow_state: Dict[str, str],
    loop_view: Dict[str, str],
    recent_cycles: List[Dict[str, str]],
) -> Dict[str, str]:
    overall_state = flow_state["overall_state"]
    current_agent = (flow_state["current_agent"] or "").strip().lower()
    active_leg = loop_view["active_leg"]
    cycle_id = recent_cycles[0]["cycle"] if recent_cycles else ""

    if overall_state == "completed":
        return {
            "loop_headline": "当前 change 已完成闭环",
            "loop_subheadline": "所有必要任务已经跑通，loop 在回到 Orchestrator 后正常收束。",
        }
    if overall_state == "paused":
        return {
            "loop_headline": "闭环停在调度器",
            "loop_subheadline": "当前没有进入下一轮，通常意味着需要人工补充信息或解除阻塞。",
        }
    if overall_state == "stuck":
        return {
            "loop_headline": "回调度器失败，loop 暂时卡住",
            "loop_subheadline": "Orchestrator 没有给出有效决策，闭环未能顺利进入下一轮。",
        }
    if overall_state == "idle":
        return {
            "loop_headline": "Loop 尚未启动",
            "loop_subheadline": "启动 harness 后，这里会显示从调度到回调度器的完整过程。",
        }
    if active_leg == "dispatch":
        return {
            "loop_headline": "Orchestrator 正在决定下一轮任务",
            "loop_subheadline": f"当前轮次{f' #{cycle_id}' if cycle_id else ''} 正停在调度段，准备派发下一个小任务。",
        }
    if active_leg == "verify":
        return {
            "loop_headline": "本轮正在测试或校验",
            "loop_subheadline": f"{current_agent or '验证 agent'} 正在确认结果能否顺利回到 Orchestrator。",
        }
    if active_leg == "return":
        return {
            "loop_headline": "本轮已结束，正在回到调度器",
            "loop_subheadline": "上一轮结果已经产生，monitor 现在强调 handoff 与下一轮入口。",
        }
    return {
        "loop_headline": "某个 agent 正在处理本轮小任务",
        "loop_subheadline": f"{current_agent or '当前 agent'} 正在执行拆分任务，完成后会进入测试或回到调度器。",
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
    recent_cycles = _build_recent_cycles(timeline_items)
    loop_view = _derive_loop_view(flow_state, recent_cycles)
    loop_copy = _loop_headline_and_subheadline(flow_state, loop_view, recent_cycles)
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
        "loop_headline": loop_copy["loop_headline"],
        "loop_subheadline": loop_copy["loop_subheadline"],
        "loop_view": loop_view,
        "recent_cycles": recent_cycles,
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

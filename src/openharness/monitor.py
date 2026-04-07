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
from typing import Dict, List, Optional, Tuple
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


HTML_PAGE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>openHarness 运行监控</title>
  <style>
    :root {
      --bg: #f4f1e8;
      --panel: #fffaf0;
      --text: #1e1d19;
      --muted: #6e695d;
      --line: #d6c9af;
      --accent: #b85c38;
      --accent-2: #2f6f62;
      --warning: #b88400;
      --danger: #9d2f2f;
      --shadow: 0 12px 30px rgba(84, 69, 42, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background:
        radial-gradient(circle at top right, rgba(184,92,56,.10), transparent 28%),
        radial-gradient(circle at left center, rgba(47,111,98,.10), transparent 32%),
        var(--bg);
      color: var(--text);
    }
    .shell {
      max-width: 1280px;
      margin: 0 auto;
      padding: 24px;
    }
    .page-hd {
      margin-bottom: 20px;
    }
    .title {
      font-size: 26px;
      margin: 0 0 6px;
      font-weight: 800;
      letter-spacing: .02em;
    }
    .title-en {
      font-size: 13px;
      font-weight: 600;
      color: var(--muted);
      margin: 0 0 10px;
    }
    .lead {
      font-size: 14px;
      color: var(--muted);
      line-height: 1.55;
      max-width: 720px;
      margin: 0;
    }
    .hero {
      display: grid;
      grid-template-columns: 1fr 320px;
      gap: 18px;
      margin-bottom: 18px;
    }
    .panel {
      background: rgba(255,250,240,.92);
      border: 1px solid var(--line);
      border-radius: 20px;
      box-shadow: var(--shadow);
      padding: 20px;
    }
    .panel-hd {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      flex-wrap: wrap;
      margin-bottom: 12px;
    }
    .panel-hd strong {
      font-size: 16px;
    }
    .panel-hd .sub {
      font-size: 12px;
      color: var(--muted);
      font-weight: 600;
    }
    .muted { color: var(--muted); }
    .grid {
      display: grid;
      grid-template-columns: repeat(12, 1fr);
      gap: 18px;
    }
    .span-4 { grid-column: span 4; }
    .span-6 { grid-column: span 6; }
    .span-8 { grid-column: span 8; }
    .span-12 { grid-column: span 12; }
    .stats {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 10px;
      margin-top: 14px;
    }
    @media (min-width: 640px) {
      .stats { grid-template-columns: repeat(4, 1fr); }
    }
    .stat {
      background: rgba(255,255,255,.7);
      border: 1px solid rgba(214,201,175,.8);
      border-radius: 14px;
      padding: 12px;
    }
    .stat .label {
      font-size: 12px;
      color: var(--muted);
      font-weight: 600;
    }
    .stat .label .en {
      display: block;
      font-size: 10px;
      text-transform: none;
      letter-spacing: 0;
      opacity: .85;
      margin-top: 2px;
    }
    .stat .value {
      font-size: 18px;
      font-weight: 800;
      margin-top: 6px;
      font-family: Consolas, "Courier New", monospace;
      word-break: break-all;
    }
    .phase-wrap { margin-top: 12px; }
    .phase-pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 14px;
      border-radius: 999px;
      background: rgba(184,92,56,.12);
      color: var(--accent);
      font-weight: 700;
    }
    .phase-pill .en {
      font-family: Consolas, "Courier New", monospace;
      font-size: 15px;
    }
    .phase-pill .zh {
      font-size: 12px;
      color: var(--muted);
      font-weight: 600;
    }
    .flow-section { margin-top: 18px; }
    .flow-caption {
      font-size: 13px;
      font-weight: 700;
      margin-bottom: 8px;
      color: var(--text);
    }
    .flow-caption .en {
      font-size: 11px;
      color: var(--muted);
      font-weight: 600;
      margin-left: 6px;
    }
    .flow-legend {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin-bottom: 10px;
    }
    .legend-pill {
      padding: 4px 9px;
      border-radius: 999px;
      font-size: 11px;
      font-weight: 700;
      border: 1px solid var(--line);
      background: rgba(255,255,255,.7);
      color: var(--muted);
    }
    .legend-pill.active {
      border-color: var(--accent);
      color: var(--accent);
      background: rgba(184,92,56,.10);
    }
    .legend-pill.done {
      border-color: rgba(47,111,98,.35);
      color: var(--accent-2);
      background: rgba(47,111,98,.10);
    }
    .legend-pill.pending {
      border-color: rgba(110,105,93,.4);
      color: var(--muted);
      background: rgba(255,255,255,.6);
    }
    .flow-canvas {
      width: 100%;
      min-height: 350px;
      border: 1px dashed rgba(214,201,175,.9);
      border-radius: 16px;
      background: rgba(255,255,255,.58);
      padding: 10px;
      overflow: auto;
    }
    .flow-diagram {
      width: 100%;
      min-width: 720px;
      height: 320px;
      display: block;
    }
    .flow-link {
      stroke: #b7aa92;
      stroke-width: 2;
      fill: none;
      marker-end: url(#arrowhead);
    }
    .flow-link.loop {
      stroke: #7b8f88;
      stroke-dasharray: 5 4;
    }
    .flow-node rect {
      fill: rgba(255,255,255,.95);
      stroke: #ccbba0;
      stroke-width: 1.4;
      rx: 12;
      ry: 12;
    }
    .flow-node text.en {
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      font-weight: 700;
      fill: #2e2c27;
    }
    .flow-node text.zh {
      font-size: 11px;
      fill: #6e695d;
    }
    .flow-node.done rect {
      fill: rgba(47,111,98,.10);
      stroke: rgba(47,111,98,.45);
    }
    .flow-node.active rect {
      fill: rgba(184,92,56,.16);
      stroke: #b85c38;
      stroke-width: 2;
    }
    .flow-node.fail rect {
      fill: rgba(157,47,47,.10);
      stroke: #9d2f2f;
      stroke-width: 2;
    }
    .loop-badge {
      display: inline-block;
      margin: 10px 0 0;
      padding: 6px 10px;
      font-size: 11px;
      font-weight: 700;
      color: var(--accent-2);
      background: rgba(47,111,98,.1);
      border-radius: 8px;
    }
    .list, .log {
      display: grid;
      gap: 10px;
      margin-top: 10px;
    }
    .item {
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255,255,255,.74);
    }
    .item .row-label {
      font-size: 11px;
      color: var(--muted);
      font-weight: 600;
      margin-bottom: 4px;
    }
    .item .row-val {
      font-family: Consolas, "Courier New", monospace;
      font-size: 13px;
      word-break: break-word;
    }
    .item strong { display: block; margin-bottom: 6px; }
    .log {
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      max-height: 360px;
      overflow: auto;
      white-space: pre-wrap;
    }
    .log-line {
      border-bottom: 1px dashed rgba(214,201,175,.55);
      padding: 6px 0;
    }
    .danger { color: var(--danger); }
    .warn { color: var(--warning); }
    .foot {
      margin-top: 12px;
      font-size: 12px;
      color: var(--muted);
    }
    .timeline-card .meta {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 14px;
      font-size: 12px;
      margin-top: 6px;
    }
    .timeline-card .meta span { color: var(--muted); }
    .timeline-card .meta code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      background: rgba(0,0,0,.04);
      padding: 2px 6px;
      border-radius: 6px;
    }
    @media (max-width: 980px) {
      .hero { grid-template-columns: 1fr; }
      .grid { grid-template-columns: 1fr; }
      .span-4, .span-6, .span-8, .span-12 { grid-column: span 1; }
      .flow-diagram {
        min-width: 620px;
        height: 360px;
      }
    }
  </style>
</head>
<body>
  <div class="shell">
    <header class="page-hd">
      <h1 class="title">openHarness 运行监控</h1>
      <p class="title-en">openHarness Monitor · read-only</p>
      <p class="lead">与 <code>hc start</code> 并行打开本页，可查看 Agent 编排与循环记录。界面为中文，<strong>Agent 名、状态字段、路径</strong>等核心技术信息保持英文。</p>
    </header>

    <div class="hero">
      <section class="panel">
        <div class="panel-hd">
          <strong>运行概览</strong>
          <span class="sub">Overview</span>
        </div>
        <div class="muted" id="subtitle" style="font-size:13px;line-height:1.5;">正在加载…</div>
        <div class="phase-wrap">
          <span class="phase-pill" id="phasePillWrap">
            <span class="en" id="phasePill">-</span>
            <span class="zh" id="phasePillZh">当前阶段</span>
          </span>
        </div>
        <div class="flow-section">
          <div class="flow-caption">任务流程 <span class="en">Agent pipeline</span></div>
          <div class="flow-legend">
            <span class="legend-pill active">当前节点 Active</span>
            <span class="legend-pill done">已完成 Done</span>
            <span class="legend-pill pending">待执行 Pending</span>
          </div>
          <div class="flow-canvas">
            <svg class="flow-diagram" viewBox="0 0 900 340" id="flowTrack" role="img" aria-label="openHarness 流程图"></svg>
          </div>
          <div class="loop-badge">循环内：Orchestrator 决策 → Coder / Tester / Fixer / Reviewer 执行（英文标识不变）</div>
        </div>
        <div class="stats">
          <div class="stat">
            <div class="label">活跃变更 <span class="en">Active change</span></div>
            <div class="value" id="activeChange">-</div>
          </div>
          <div class="stat">
            <div class="label">当前 Agent <span class="en">Role</span></div>
            <div class="value" id="currentAgent">-</div>
          </div>
          <div class="stat">
            <div class="label">主循环轮次 <span class="en">Cycle</span></div>
            <div class="value" id="currentCycle">-</div>
          </div>
          <div class="stat">
            <div class="label">功能进度 <span class="en">Progress</span></div>
            <div class="value" id="progressValue">-</div>
          </div>
        </div>
      </section>
      <section class="panel">
        <div class="panel-hd">
          <strong>运行快照</strong>
          <span class="sub">Snapshot</span>
        </div>
        <div class="list" id="snapshot"></div>
        <div class="foot" id="lastUpdated">上次刷新：-</div>
      </section>
    </div>

    <div class="grid">
      <section class="panel span-8">
        <div class="panel-hd">
          <strong>循环时间线</strong>
          <span class="sub">Recent cycles（Orchestrator 决策见 dev-log；此处为 worker 循环块）</span>
        </div>
        <div class="list" id="timeline"></div>
      </section>
      <section class="panel span-4">
        <div class="panel-hd">
          <strong>阻塞项</strong>
          <span class="sub">missing_info</span>
        </div>
        <div class="list" id="blockers"></div>
      </section>
      <section class="panel span-6">
        <div class="panel-hd">
          <strong>功能清单</strong>
          <span class="sub">feature_list</span>
        </div>
        <div class="list" id="features"></div>
      </section>
      <section class="panel span-6">
        <div class="panel-hd">
          <strong>测试与审查</strong>
          <span class="sub">test_report / review_report</span>
        </div>
        <div class="list" id="quality"></div>
      </section>
      <section class="panel span-12">
        <div class="panel-hd">
          <strong>最近日志</strong>
          <span class="sub">dev-log.txt tail</span>
        </div>
        <div class="log" id="logs"></div>
      </section>
    </div>
  </div>
  <script>
    const stages = ["Initializer", "Orchestrator", "Coder", "Tester", "Fixer", "Reviewer"];
    const stagesZh = ["初始化", "编排", "编码", "测试", "修复", "审查"];

    function phaseZh(enPhase) {
      const p = (enPhase || "").toLowerCase();
      const map = {
        "initializer": "初始化",
        "orchestrator": "编排决策",
        "coder": "编码",
        "tester": "测试",
        "fixer": "修复",
        "reviewer": "审查",
        "completed": "已完成",
        "paused": "已暂停",
        "stuck": "卡住",
        "idle": "空闲",
        "initializing": "初始化中",
        "unknown": "未知"
      };
      for (const k of Object.keys(map)) {
        if (p.includes(k)) return map[k];
      }
      return "运行中";
    }

    function stageState(currentPhase, stageName) {
      const phase = (currentPhase || "").toLowerCase();
      const stage = stageName.toLowerCase();
      if (phase.includes(stage)) return "active";
      const order = stages.map(s => s.toLowerCase());
      const currentIndex = order.findIndex(v => phase.includes(v));
      const stageIndex = order.indexOf(stage);
      if (currentIndex > stageIndex) return "done";
      return "";
    }

    function hasFailureState(summary) {
      const txt = `${summary.latest_status || ""} ${summary.current_phase || ""} ${summary.overall_test_status || ""} ${summary.overall_review_status || ""}`.toLowerCase();
      return txt.includes("error") || txt.includes("fail") || txt.includes("stuck");
    }

    function phaseToStage(phase) {
      const p = (phase || "").toLowerCase();
      if (p.includes("initializer") || p.includes("initializing")) return "Initializer";
      if (p.includes("orchestrator")) return "Orchestrator";
      if (p.includes("coder")) return "Coder";
      if (p.includes("tester")) return "Tester";
      if (p.includes("fixer")) return "Fixer";
      if (p.includes("reviewer")) return "Reviewer";
      return "";
    }

    function renderFlow(summary) {
      const track = document.getElementById("flowTrack");
      const activeStage = phaseToStage(summary.current_phase);
      const hasFail = hasFailureState(summary);

      const nodeMap = {
        "Initializer": { x: 70,  y: 30 },
        "Orchestrator": { x: 360, y: 30 },
        "Coder": { x: 650, y: 20 },
        "Tester": { x: 650, y: 100 },
        "Fixer": { x: 650, y: 180 },
        "Reviewer": { x: 650, y: 260 }
      };
      const w = 170;
      const h = 56;

      const links = [
        ["Initializer", "Orchestrator", false],
        ["Orchestrator", "Coder", false],
        ["Orchestrator", "Tester", false],
        ["Orchestrator", "Fixer", false],
        ["Orchestrator", "Reviewer", false],
        ["Coder", "Orchestrator", true],
        ["Tester", "Orchestrator", true],
        ["Fixer", "Orchestrator", true],
        ["Reviewer", "Orchestrator", true]
      ];

      const order = stages;
      const activeIndex = order.indexOf(activeStage);
      const defs = `
        <defs>
          <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
            <polygon points="0 0, 8 3, 0 6" fill="#b7aa92"></polygon>
          </marker>
        </defs>
      `;

      const linkSvg = links.map(([from, to, loop]) => {
        const f = nodeMap[from];
        const t = nodeMap[to];
        const x1 = f.x + w;
        const y1 = f.y + (h / 2);
        const x2 = t.x;
        const y2 = t.y + (h / 2);
        let d = `M ${x1} ${y1} L ${x2} ${y2}`;
        if (loop) {
          const cp1x = x1 + 40;
          const cp2x = x2 - 40;
          d = `M ${x1} ${y1} C ${cp1x} ${y1}, ${cp2x} ${y2}, ${x2} ${y2}`;
        }
        return `<path class="flow-link ${loop ? "loop" : ""}" d="${d}"></path>`;
      }).join("");

      const nodesSvg = stages.map((st, idx) => {
        const pos = nodeMap[st];
        let state = "pending";
        if (idx <= activeIndex && activeIndex >= 0) state = "done";
        if (st === activeStage) state = hasFail ? "fail" : "active";
        const zh = stagesZh[idx];
        return `
          <g class="flow-node ${state}">
            <rect x="${pos.x}" y="${pos.y}" width="${w}" height="${h}"></rect>
            <text class="en" x="${pos.x + 12}" y="${pos.y + 23}">${st}</text>
            <text class="zh" x="${pos.x + 12}" y="${pos.y + 41}">${zh}</text>
          </g>
        `;
      }).join("");

      track.innerHTML = `${defs}${linkSvg}${nodesSvg}`;
    }

    function renderList(id, items, emptyText, mapper) {
      const root = document.getElementById(id);
      if (!items || items.length === 0) {
        root.innerHTML = `<div class="item muted">${emptyText}</div>`;
        return;
      }
      root.innerHTML = items.map(mapper).join("");
    }

    function escapeHtml(text) {
      return String(text || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
    }

    async function loadDashboard() {
      const [summary, timeline, logs, blockers, features] = await Promise.all([
        fetch("/api/monitor/summary").then(r => r.json()),
        fetch("/api/monitor/timeline").then(r => r.json()),
        fetch("/api/monitor/logs").then(r => r.json()),
        fetch("/api/monitor/blockers").then(r => r.json()),
        fetch("/api/monitor/features").then(r => r.json())
      ]);

      const phaseEn = summary.current_phase || "-";
      document.getElementById("subtitle").innerHTML =
        `<strong>project_id</strong> <code>${escapeHtml(summary.project_id || "-")}</code> · ` +
        `<strong>backend</strong> <code>${escapeHtml(summary.backend || "-")}</code><br>` +
        `<span class="muted">project_dir:</span> <code style="font-size:11px;">${escapeHtml(summary.project_dir || "-")}</code>`;
      document.getElementById("phasePill").textContent = phaseEn;
      document.getElementById("phasePillZh").textContent = phaseZh(phaseEn);
      document.getElementById("activeChange").textContent = summary.active_change || "legacy-flat-input";
      document.getElementById("currentAgent").textContent = summary.current_agent || "-";
      document.getElementById("currentCycle").textContent = summary.current_cycle || "-";
      document.getElementById("progressValue").textContent =
        summary.progress ? `${summary.progress.passing}/${summary.progress.total} (${summary.progress.percent}%)` : "-";
      document.getElementById("lastUpdated").textContent = `上次刷新：${summary.last_update_time || "-"}`;
      renderFlow(summary);

      renderList("snapshot", [
        { zh: "当前阶段（英文）", en: "current_phase", value: summary.current_phase || "-" },
        { zh: "当前 Agent 标识", en: "current_agent", value: summary.current_agent || "-" },
        { zh: "最近 worker 状态", en: "latest_status", value: summary.latest_status || "-" },
        { zh: "变更标题", en: "active_change_title", value: summary.active_change_title || "-" }
      ], "暂无快照数据。", (item) =>
        `<div class="item">
          <div class="row-label">${escapeHtml(item.zh)} · ${escapeHtml(item.en)}</div>
          <div class="row-val">${escapeHtml(item.value)}</div>
        </div>`
      );

      renderList("timeline", timeline.items, "尚无循环记录（请先运行 hc start，或等待产生 cycle-log）。", (item) =>
        `<div class="item timeline-card">
          <strong>Cycle ${escapeHtml(item.cycle)} · <span class="en">${escapeHtml(item.agent || "-")}</span></strong>
          <div class="meta">
            <span>时间</span> <code>${escapeHtml(item.time || "-")}</code>
            <span>status</span> <code>${escapeHtml(item.status || "-")}</code>
            <span>duration</span> <code>${escapeHtml(item.duration || "-")}</code>
          </div>
          <div class="muted" style="margin-top:8px;font-size:12px;"><span class="muted">args:</span> <code>${escapeHtml(item.args || "")}</code></div>
        </div>`
      );

      renderList("blockers", blockers.items, "当前无阻塞项。", (item) =>
        `<div class="item">
          <strong class="${item.status === 'pending' ? 'danger' : ''}">${escapeHtml(item.id || "id")}</strong>
          <div style="margin-top:6px;">${escapeHtml(item.desc || item.description || "-")}</div>
          <div class="muted" style="margin-top:6px;font-size:12px;">status: <code>${escapeHtml(item.status || "-")}</code></div>
        </div>`
      );

      renderList("features", features.items.slice(0, 16), "尚无功能项。", (item) =>
        `<div class="item">
          <div class="row-val"><strong>${escapeHtml(String(item.id || "-"))}</strong> · <code>${escapeHtml(item.status || "-")}</code></div>
          <div style="margin-top:6px;font-size:13px;">${escapeHtml(item.description || item.name || "-")}</div>
        </div>`
      );

      renderList("quality", [
        { zh: "测试总览", en: "test_report.overall", value: summary.overall_test_status || "unknown" },
        { zh: "审查总览", en: "review_report.overall", value: summary.overall_review_status || "unknown" },
        { zh: "待处理阻塞数", en: "pending_blockers", value: String(summary.pending_blockers || 0) },
      ], "暂无质量汇总。", (item) =>
        `<div class="item">
          <div class="row-label">${escapeHtml(item.zh)} · ${escapeHtml(item.en)}</div>
          <div class="row-val">${escapeHtml(item.value)}</div>
        </div>`
      );

      renderList("logs", logs.items, "暂无日志。", (line) =>
        `<div class="log-line">${escapeHtml(line)}</div>`
      );
    }

    loadDashboard();
    setInterval(loadDashboard, """ + str(DEFAULT_REFRESH_MS) + """);
  </script>
</body>
</html>
"""


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
            file_size = handle.tell()
            seek_to = max(file_size - max_bytes, 0)
            handle.seek(seek_to)
            data = handle.read().decode("utf-8", errors="replace")
        lines = [line.rstrip("\n") for line in data.splitlines() if line.strip()]
        return lines[-limit:]
    except Exception:
        return []


def _parse_cycle_blocks(path: Path, limit: int = DEFAULT_TIMELINE_LIMIT) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    segments = re.split(r"\n=+\n", text)
    items: List[Dict[str, str]] = []
    for segment in segments:
        if "Cycle:" not in segment:
            continue
        item: Dict[str, str] = {}
        for line in segment.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            key = key.strip().lower()
            value = value.strip()
            if key == "cycle":
                item["cycle"] = value
            elif key == "time":
                item["time"] = value
            elif key == "agent":
                item["agent"] = value
            elif key == "args":
                item["args"] = value
            elif key == "duration":
                item["duration"] = value
            elif key == "status":
                item["status"] = value
        if item:
            items.append(item)
    return items[-limit:]


def _phase_from_logs(log_lines: List[str], timeline_items: List[Dict[str, str]], feature_data, missing_info) -> Tuple[str, str]:
    pending_blockers = [
        item for item in missing_info.get("missing_items", [])
        if item.get("status", "pending") == "pending"
    ]
    latest_log = log_lines[-1] if log_lines else ""

    if any("PROJECT COMPLETE" in line.upper() for line in log_lines[-10:]):
        return "Completed", "complete"
    if "PAUSED" in latest_log.upper() or pending_blockers:
        return "Paused", "pause_for_human"
    if "STUCK" in latest_log.upper():
        return "Stuck", "stuck"
    if "Calling orchestrator" in latest_log:
        return "Orchestrator", "orchestrator"

    if timeline_items:
        latest = timeline_items[-1]
        agent = latest.get("agent", "").lower()
        phase_map = {
            "initializer": "Initializer",
            "orchestrator": "Orchestrator",
            "coder": "Coder",
            "tester": "Tester",
            "fixer": "Fixer",
            "reviewer": "Reviewer",
        }
        if agent in phase_map:
            return phase_map[agent], agent

    if feature_data:
        return "Orchestrator", "orchestrator"
    if log_lines:
        return "Initializing", "initializer"
    return "Idle", ""


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

    current_phase, current_agent = _phase_from_logs(log_lines, timeline_items, feature_data, missing_info)
    progress = get_progress(feature_data) if feature_data else None
    blockers = missing_info.get("missing_items", []) if isinstance(missing_info, dict) else []
    pending_blockers = [
        item for item in blockers
        if isinstance(item, dict) and item.get("status", "pending") == "pending"
    ]

    latest_status = timeline_items[-1]["status"] if timeline_items else ""
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
        "current_phase": current_phase,
        "current_agent": current_agent,
        "current_cycle": current_cycle,
        "latest_status": latest_status,
        "last_update_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "progress": progress,
        "overall_test_status": test_report.get("overall", "unknown") if isinstance(test_report, dict) else "unknown",
        "overall_review_status": review_report.get("overall", "unknown") if isinstance(review_report, dict) else "unknown",
        "pending_blockers": len(pending_blockers),
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
            payload = {k: v for k, v in snapshot.items() if k not in ("timeline", "logs", "blockers", "features")}
            self._write_json(payload)
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

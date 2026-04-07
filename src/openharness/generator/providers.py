"""Requirement generation providers."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    from openharness.backend import CodexBackend
    from openharness.generator.context import ProjectContext, summarize_project_context
except ImportError:
    from backend import CodexBackend
    from generator.context import ProjectContext, summarize_project_context


SUPPORTED_GENERATOR_PROVIDERS = ("openspec", "codex", "template")
DEFAULT_GENERATOR_PROVIDER = "openspec"


@dataclass
class GenerationRequest:
    """User request normalized for providers."""

    prompt: str
    mode: str
    overwrite: bool = False
    model: Optional[str] = None


@dataclass
class GenerationOutcome:
    """Structured provider output before files are written."""

    provider: str
    title: str
    prd_content: str = ""
    techspec_content: str = ""
    tech_stack_content: str = ""
    warnings: List[str] = field(default_factory=list)
    missing_info: List[str] = field(default_factory=list)


class GeneratorProvider:
    """Base class for requirement generation providers."""

    name = ""

    def is_available(self) -> bool:
        return True

    def get_unavailable_reason(self) -> str:
        return ""

    def generate(self, request: GenerationRequest, context: ProjectContext) -> GenerationOutcome:
        raise NotImplementedError


def resolve_generator_provider_name(name: Optional[str] = None, config_provider: Optional[str] = None) -> str:
    if name:
        normalized = name.strip().lower()
        if normalized in SUPPORTED_GENERATOR_PROVIDERS:
            return normalized
    if config_provider:
        normalized = config_provider.strip().lower()
        if normalized in SUPPORTED_GENERATOR_PROVIDERS:
            return normalized
    return DEFAULT_GENERATOR_PROVIDER


def slugify_prompt(prompt: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", prompt).strip("-").lower()
    if cleaned:
        return cleaned[:40]
    digest = hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:8]
    return f"generated-{digest}"


def _format_bullets(items: List[str], fallback: str = "- TBD") -> str:
    if not items:
        return fallback
    return "\n".join(f"- {item}" for item in items)


def _build_stack_lines(context: ProjectContext) -> List[str]:
    if context.tech_stack_text:
        return [line.strip() for line in context.tech_stack_text.splitlines() if line.strip()]

    detected = [f"- {item}" for item in context.detected_stack]
    if detected:
        return detected

    return [
        "- Frontend: TBD",
        "- Backend: TBD",
        "- Package Manager: TBD",
        "- Test: TBD",
        "- AI Backend: codex/opencode/claude",
    ]


def _infer_missing_info(prompt: str, context: ProjectContext) -> List[str]:
    missing: List[str] = []
    lowered = prompt.lower()

    if not context.tech_stack_text and not context.detected_stack:
        missing.append("项目技术栈尚未明确，需要补充前后端、包管理与测试工具。")
    if any(keyword in lowered for keyword in ("login", "auth", "登录")) and not any(
        keyword in lowered for keyword in ("jwt", "oauth", "session", "token", "localstorage", "账号", "密码")
    ):
        missing.append("登录能力的鉴权方式、账号来源和会话保存策略尚未明确。")
    if len(prompt.strip()) < 12:
        missing.append("需求描述较短，建议补充页面范围、边界条件和异常流程。")
    if "api" not in lowered and "接口" not in prompt and "localstorage" not in lowered and "数据库" not in prompt:
        missing.append("尚未明确数据来源或持久化方案，需要补充接口、数据库或本地存储策略。")

    deduped: List[str] = []
    seen = set()
    for item in missing:
        if item in seen:
            continue
        deduped.append(item)
        seen.add(item)
    return deduped[:4]


def _build_title(prompt: str) -> str:
    title = prompt.strip().replace('"', "")
    return title or "Generated Change"


def _build_template_outcome(provider_name: str, request: GenerationRequest, context: ProjectContext) -> GenerationOutcome:
    title = _build_title(request.prompt)
    missing_info = _infer_missing_info(request.prompt, context)
    stack_text = "\n".join(_build_stack_lines(context))
    detected_stack = ", ".join(context.detected_stack) if context.detected_stack else "TBD"
    output_zh = context.output_language.startswith("zh")

    if output_zh:
        tech_stack_content = (
            "# Tech Stack\n\n"
            f"{stack_text}\n\n"
            "## Notes\n\n"
            f"- Generated for requirement: {title}\n"
            "- This file is safe to edit manually after generation.\n"
        )
        prd_content = (
            f"# 需求说明\n\n"
            f"## 标题\n\n- {title}\n\n"
            "## 目标\n\n"
            "- 明确该变更要解决的用户问题和业务目标。\n"
            "- 保持实现与现有项目结构兼容。\n\n"
            "## 用户故事\n\n"
            "- 作为最终用户，我希望能够完成该需求的主流程并获得明确反馈。\n"
            "- 作为开发者，我希望该能力遵循当前项目技术栈和目录结构。\n\n"
            "## 功能范围\n\n"
            f"- 实现需求：{title}\n"
            "- 先交付最小可运行路径，不引入与现有项目冲突的结构。\n"
            "- 若信息不足，记录待补充项并继续生成可执行说明。\n\n"
            "## 验收标准\n\n"
            "- 主流程可执行。\n"
            "- 关键边界条件有明确处理。\n"
            "- 结果与当前项目技术栈保持一致。\n"
            "- 有清晰的测试或手动验证步骤。\n\n"
            "## 非功能约束\n\n"
            f"- 推断技术栈：{detected_stack}\n"
            "- 保持 Harness 主循环和状态文件契约不变。\n"
        )
        techspec_content = (
            f"# 技术方案\n\n"
            f"## 需求主题\n\n- {title}\n\n"
            "## 实现边界\n\n"
            "- 在当前项目目录中完成该变更的最小可运行实现。\n"
            "- 优先扩展现有页面、模块或服务。\n"
            "- 保持现有输入输出契约和目录结构兼容。\n\n"
            "## 推荐实现\n\n"
            f"- 技术栈参考：{detected_stack}\n"
            "- 先梳理现有入口、状态来源和持久化方式。\n"
            "- 将工作拆成页面或模块、交互逻辑、状态管理、校验、测试几个层面。\n"
            "- 为关键流程补最小验证路径，避免只交付静态界面。\n\n"
            "## 数据与状态\n\n"
            "- 明确输入、输出、状态保存位置和失败回退逻辑。\n"
            "- 若项目无后端接口，优先使用本地状态或 localStorage 模拟。\n\n"
            "## 测试与验收\n\n"
            "- 补充最小单元测试、静态检查或手动验证步骤。\n"
            "- 覆盖主流程、异常流程和关键边界场景。\n"
        )
    else:
        tech_stack_content = (
            "# Tech Stack\n\n"
            f"{stack_text}\n\n"
            "## Notes\n\n"
            f"- Generated for requirement: {title}\n"
            "- This file is safe to edit manually after generation.\n"
        )
        prd_content = (
            f"# Product Requirement\n\n"
            f"## Title\n\n- {title}\n\n"
            "## Goal\n\n"
            "- Clarify the user problem and business goal for this change.\n"
            "- Keep the implementation aligned with the current repository structure.\n\n"
            "## User Stories\n\n"
            "- As an end user, I want the primary workflow to succeed with clear feedback.\n"
            "- As a developer, I want the change to follow the existing stack and layout.\n\n"
            "## Scope\n\n"
            f"- Implement the requested capability: {title}\n"
            "- Deliver the smallest workable path first.\n"
            "- Record missing details while still generating executable guidance.\n\n"
            "## Acceptance Criteria\n\n"
            "- The primary workflow is executable.\n"
            "- Key edge cases have a defined handling strategy.\n"
            "- The result follows the detected project stack.\n"
            "- Verification steps are clear and reproducible.\n\n"
            "## Non-Functional Constraints\n\n"
            f"- Detected stack: {detected_stack}\n"
            "- Preserve the existing Harness loop and state-file contract.\n"
        )
        techspec_content = (
            f"# Technical Specification\n\n"
            f"## Requirement Topic\n\n- {title}\n\n"
            "## Implementation Boundary\n\n"
            "- Deliver the smallest workable implementation in this repository.\n"
            "- Prefer incremental edits to existing pages, modules, and services.\n"
            "- Preserve current input/output contracts and folder layout.\n\n"
            "## Recommended Approach\n\n"
            f"- Stack reference: {detected_stack}\n"
            "- Inspect the current entry points, state sources, and persistence strategy first.\n"
            "- Split the work into UI or module changes, interaction logic, state handling, validation, and testing.\n"
            "- Add a minimal verification path so the result is more than a static stub.\n\n"
            "## Data And State\n\n"
            "- Define inputs, outputs, persistence location, and fallback behavior.\n"
            "- If no backend API exists, prefer local state or localStorage as a placeholder.\n\n"
            "## Verification\n\n"
            "- Add the smallest useful tests, checks, or manual verification steps.\n"
            "- Cover the primary flow, error flow, and key edge cases.\n"
        )

    return GenerationOutcome(
        provider=provider_name,
        title=title,
        prd_content=prd_content,
        techspec_content=techspec_content,
        tech_stack_content=tech_stack_content,
        missing_info=missing_info,
    )


class OpenSpecProvider(GeneratorProvider):
    """Provider name kept for compatibility, output follows Harness SDD change format."""

    name = "openspec"

    def generate(self, request: GenerationRequest, context: ProjectContext) -> GenerationOutcome:
        return _build_template_outcome(self.name, request, context)


class TemplateProvider(GeneratorProvider):
    """Local deterministic fallback provider."""

    name = "template"

    def generate(self, request: GenerationRequest, context: ProjectContext) -> GenerationOutcome:
        outcome = _build_template_outcome(self.name, request, context)
        outcome.warnings.append("Using local template provider; content is generated without an external model.")
        return outcome


class CodexProvider(GeneratorProvider):
    """Use Codex CLI to draft change content, then normalize it."""

    name = "codex"

    def __init__(self):
        self.backend = CodexBackend()

    def is_available(self) -> bool:
        return self.backend.is_installed()

    def get_unavailable_reason(self) -> str:
        return "Codex CLI is not installed or not in PATH."

    def generate(self, request: GenerationRequest, context: ProjectContext) -> GenerationOutcome:
        fallback = _build_template_outcome(self.name, request, context)
        if not self.is_available():
            fallback.warnings.append(self.get_unavailable_reason() + " Falling back to structured local generation.")
            return fallback

        payload = self._generate_with_codex(request, context)
        if not payload:
            fallback.warnings.append(
                "Codex generation returned no structured payload. Falling back to structured local generation."
            )
            return fallback

        title = str(payload.get("title", "")).strip() or fallback.title
        prd_content = str(payload.get("prd", "")).strip() or fallback.prd_content
        techspec_content = str(payload.get("techspec", "")).strip() or fallback.techspec_content
        tech_stack_content = str(payload.get("tech_stack", "")).strip() or fallback.tech_stack_content
        missing_info = payload.get("missing_info")
        if not isinstance(missing_info, list):
            missing_info = fallback.missing_info
        else:
            missing_info = [str(item).strip() for item in missing_info if str(item).strip()]

        return GenerationOutcome(
            provider=self.name,
            title=title,
            prd_content=prd_content,
            techspec_content=techspec_content,
            tech_stack_content=tech_stack_content,
            warnings=["Content drafted with Codex CLI and normalized into the Harness SDD output contract."],
            missing_info=missing_info,
        )

    def _generate_with_codex(self, request: GenerationRequest, context: ProjectContext) -> Dict[str, object]:
        prompt = (
            "Return JSON only. No markdown fences, no commentary.\n\n"
            "Generate openHarness SDD change documents for the following software requirement.\n"
            "The JSON object must use these keys: title, tech_stack, prd, techspec, missing_info.\n"
            "tech_stack, prd, and techspec must be markdown strings. missing_info must be an array of strings.\n\n"
            f"Request mode: {request.mode}\n"
            f"User requirement: {request.prompt}\n\n"
            "Project context:\n"
            f"{summarize_project_context(context)}"
        )

        cmd_path = self.backend.get_command_path()
        if sys.platform == "win32":
            cmd = ["cmd", "/c", cmd_path, "exec", "--full-auto", "--skip-git-repo-check", "--color", "never"]
        else:
            cmd = [cmd_path, "exec", "--full-auto", "--skip-git-repo-check", "--color", "never"]
        if request.model:
            cmd.extend(["--model", request.model])
        cmd.append(prompt)

        try:
            result = subprocess.run(
                cmd,
                cwd=str(context.project_dir),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
            )
        except Exception:
            return {}

        if result.returncode != 0 or not result.stdout:
            return {}

        return self._extract_json(result.stdout)

    @staticmethod
    def _extract_json(output: str) -> Dict[str, object]:
        text = output.strip()
        if not text:
            return {}
        try:
            payload = json.loads(text)
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        try:
            payload = json.loads(match.group(0))
            return payload if isinstance(payload, dict) else {}
        except json.JSONDecodeError:
            return {}


_PROVIDERS = {
    "openspec": OpenSpecProvider,
    "codex": CodexProvider,
    "template": TemplateProvider,
}


def get_generator_provider(name: str) -> GeneratorProvider:
    provider_name = resolve_generator_provider_name(name)
    provider_cls = _PROVIDERS.get(provider_name, OpenSpecProvider)
    return provider_cls()

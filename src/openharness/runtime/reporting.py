"""Logging, notifications, and report generation."""

from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

from .context import CYCLE_LOG_FILENAME, REPORTS_DIRNAME
from .state import get_changes, get_features_from_data, get_progress

try:
    from openharness.utils.config import get_project_config_file
except ImportError:  # pragma: no cover
    from utils.config import get_project_config_file


class RuntimeReporter:
    """Handles logs, notifications, and dev reports."""

    def __init__(self, runtime, state_store):
        self.runtime = runtime
        self.state_store = state_store

    def get_webhook_url(self):
        config_path = get_project_config_file(self.runtime.project_dir)
        if os.path.exists(config_path):
            if yaml is not None:
                try:
                    with open(config_path, "r", encoding="utf-8") as handle:
                        config = yaml.safe_load(handle)
                    if config and isinstance(config, dict):
                        url = config.get("webhook_url", "")
                        return url.strip() if url else ""
                except Exception:
                    pass
            else:
                try:
                    with open(config_path, "r", encoding="utf-8") as handle:
                        for line in handle:
                            if line.startswith("webhook_url:"):
                                return line.split(":", 1)[1].strip().strip('"').strip("'")
                except Exception:
                    pass
        return os.environ.get("OPENHARNESS_WEBHOOK_URL", "") or os.environ.get(
            "HARNESSCODE_WEBHOOK_URL", ""
        )

    def log(self, message, to_file_only=False):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(self.runtime.paths.log_file, "a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
        if not to_file_only:
            print(f"[{timestamp}] {message}")

    def log_cycle_detail(self, iteration, agent, args, duration, status, output_summary):
        cycle_log_file = os.path.join(self.runtime.paths.openharness_dir, CYCLE_LOG_FILENAME)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(cycle_log_file, "a", encoding="utf-8") as handle:
            handle.write(f"\n{'=' * 80}\n")
            handle.write(f"Cycle: {iteration}\n")
            handle.write(f"Time: {timestamp}\n")
            handle.write(f"Agent: {agent}\n")
            handle.write(f"Args: {args}\n")
            handle.write(f"Duration: {duration:.2f}s\n")
            handle.write(f"Status: {status}\n")
            handle.write(f"Output Summary:\n{output_summary}\n")
            handle.write(f"{'=' * 80}\n")

    def send_im_message(self, message):
        webhook_url = self.get_webhook_url()
        if not webhook_url:
            return False
        try:
            body = json.dumps({"text": message}).encode("utf-8")
            request = Request(
                webhook_url,
                data=body,
                headers={"Content-Type": "application/json; charset=utf-8"},
                method="POST",
            )
            with urlopen(request, timeout=10) as response:
                if response.status == 200:
                    self.log("[IM] Message sent successfully", to_file_only=True)
                    return True
        except (URLError, HTTPError, Exception) as exc:
            self.log(f"[IM] Failed to send message: {str(exc)}")
        return False

    def should_generate_report(self):
        data = self.state_store.read_feature_list()
        features = get_features_from_data(data) if data else []
        has_features = len(features) > 0
        has_code_changes = False

        start_commit_result = subprocess.run(
            ["git", "rev-list", "--max-parents=0", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=self.runtime.project_dir,
            timeout=10,
        )
        if start_commit_result.returncode == 0:
            initial_commit = start_commit_result.stdout.strip()
            diff_result = subprocess.run(
                ["git", "diff", "--stat", initial_commit],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.runtime.project_dir,
            )
            has_code_changes = diff_result.returncode == 0 and bool(diff_result.stdout.strip())

        return has_features or has_code_changes

    def check_and_notify_progress(self):
        current_data = self.state_store.read_feature_list()
        if not current_data:
            return

        if self.runtime.last_feature_list is None:
            progress = get_progress(current_data)
            if progress:
                message = (
                    f"[Monitor Started] Current: {progress['passing']}/"
                    f"{progress['total']} ({progress['percent']}%)"
                )
                self.send_im_message(message)
                self.log(
                    f"[Monitor] Initial state: {progress['passing']}/"
                    f"{progress['total']} ({progress['percent']}%)"
                )
        else:
            changes = get_changes(self.runtime.last_feature_list, current_data)
            if changes:
                progress = get_progress(current_data)
                if progress:
                    message = (
                        f"[Progress Update] {progress['passing']}/{progress['total']} "
                        f"({progress['percent']}%)\n\nChanges:\n" + "\n".join(changes)
                    )
                    self.send_im_message(message)
                    self.log(f"[Monitor] Changes detected: {len(changes)}")

        self.runtime.last_feature_list = current_data

    def generate_dev_report(self, start_commit=None, report_type="final"):
        if not self.should_generate_report():
            self.log("[Report] No progress to report, skipping report generation")
            return None

        report_dir = Path(self.runtime.paths.openharness_dir) / REPORTS_DIRNAME
        report_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if report_type == "final":
            report_file = report_dir / f"dev-report-final-{timestamp}.md"
        else:
            report_file = report_dir / f"dev-report-partial-{timestamp}.md"

        lines = [
            f"# Development Report ({report_type.title()})",
            "",
            f"> Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"> Project: {self.runtime.project_id}",
            f"> Report Type: {report_type}",
            "",
            "---",
            "",
            "## Summary",
            "",
        ]

        feature_data = {"total": 0, "completed": 0, "pending": 0}
        data = self.state_store.read_feature_list()
        if data:
            features = get_features_from_data(data)
            feature_data["total"] = len(features)
            feature_data["completed"] = sum(
                1 for feature in features if feature.get("status") == "completed"
            )
            feature_data["pending"] = sum(
                1 for feature in features if feature.get("status") == "pending"
            )

        lines.extend(
            [
                "| Metric | Value |",
                "|--------|-------|",
                f"| Total Features | {feature_data['total']} |",
                f"| Completed | {feature_data['completed']} |",
                f"| Pending | {feature_data['pending']} |",
                "",
                "---",
                "",
                "## Code Statistics",
                "",
            ]
        )

        if start_commit:
            result = subprocess.run(
                ["git", "diff", "--stat", start_commit],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                cwd=self.runtime.project_dir,
            )
            if result.returncode == 0 and result.stdout.strip():
                lines.extend(["```", result.stdout.strip(), "```"])
            else:
                lines.append("N/A")
        else:
            lines.append("N/A (no start commit recorded)")

        lines.extend(["", "---", "", "## Agent Success Rates", ""])

        if self.runtime.metrics:
            for agent in ["orchestrator", "coder", "tester", "fixer", "reviewer"]:
                rate = self.runtime.metrics.get_success_rate(agent)
                lines.append(f"- {agent}: {rate:.1%}")
        else:
            lines.append("N/A")

        lines.extend(
            [
                "",
                "---",
                "",
                "## Development Log",
                "",
                "See: dev-log.txt",
                "See: .openharness/cycle-log.txt (detailed cycle logs)",
                "",
            ]
        )

        report_file.write_text("\n".join(lines), encoding="utf-8")
        self.log(f"[Report] Generated: {report_file}")
        return str(report_file)

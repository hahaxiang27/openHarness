"""Runtime state loading and decision helpers."""

import json
import os
import re


def parse_orchestrator_decision(output):
    match = re.search(
        r"---\s*ORCHESTRATOR\s+NEXT:\s*(\w+)(?:\s+(.+?))?\s*---",
        output,
        re.IGNORECASE,
    )
    if match:
        agent = match.group(1).lower()
        args = match.group(2).strip() if match.group(2) else ""
        return agent, args

    if "PROJECT COMPLETE" in output.upper():
        return "complete", ""

    return None, None


def parse_agent_output_status(output):
    match = re.search(
        r"---\s*AGENT\s+COMPLETE:\s*(\w+)\s*-\s*(\w+)\s*-\s*(\w+)\s*---",
        output,
        re.IGNORECASE,
    )
    if match:
        return {
            "agent": match.group(1).lower(),
            "status": match.group(2).lower(),
            "module": match.group(3).lower(),
        }
    return None


def normalize_feature_status(status):
    """Normalize AI-written feature status values."""
    if not status:
        return "pending"
    normalized = status.strip().lower()
    if normalized in ("completed", "done", "finish", "finished", "complete", "passed"):
        return "completed"
    return normalized


def normalize_feature_list(data):
    """Normalize the status field of all features in feature_list."""
    if not data:
        return data
    if isinstance(data, list):
        for feature in data:
            if isinstance(feature, dict) and "status" in feature:
                feature["status"] = normalize_feature_status(feature["status"])
    elif isinstance(data, dict) and "features" in data:
        for feature in data["features"]:
            if isinstance(feature, dict) and "status" in feature:
                feature["status"] = normalize_feature_status(feature["status"])
    return data


def get_features_from_data(data):
    """Return features uniformly from list or dict feature payloads."""
    if not data:
        return []
    if isinstance(data, list):
        return data
    return data.get("features", [])


def get_progress(data):
    if not data:
        return None
    features = get_features_from_data(data)
    total = len(features)
    passing = sum(1 for feature in features if feature.get("status") == "completed")
    percent = round((passing / total) * 100, 1) if total > 0 else 0
    return {"total": total, "passing": passing, "percent": percent}


def get_changes(old_data, new_data):
    if not old_data or not new_data:
        return []

    changes = []
    old_features = {feature.get("id"): feature for feature in get_features_from_data(old_data)}

    for new_feature in get_features_from_data(new_data):
        feature_id = new_feature.get("id")
        old_feature = old_features.get(feature_id)
        if old_feature and old_feature.get("status") != new_feature.get("status"):
            status = "[PASS]" if new_feature.get("status") == "completed" else "[FAIL]"
            name = new_feature.get("name") or new_feature.get("description", "")[:30]
            changes.append(f"{status} {feature_id}: {name}")

    return changes


def get_pending_feature_ids(data):
    return [feature.get("id") for feature in get_features_from_data(data) if feature.get("status") == "pending"]


def is_false_completion(feature_data, test_report=None, review_report=None):
    pending_ids = get_pending_feature_ids(feature_data)
    if pending_ids:
        return True, {"reason": "pending_features", "pending_ids": pending_ids}
    if test_report and test_report.get("overall") == "fail":
        return True, {"reason": "test_report_failed", "pending_ids": []}
    if review_report and review_report.get("overall") == "fail":
        return True, {"reason": "review_report_failed", "pending_ids": []}
    return False, {"reason": "", "pending_ids": []}


def update_same_decision_state(last_decision, current_decision, current_count):
    if current_decision and current_decision == last_decision:
        return last_decision, current_count + 1
    return current_decision, 1


class RuntimeStateStore:
    """State file accessor with normalization and lightweight reuse."""

    def __init__(self, paths, log):
        self.paths = paths
        self.log = log

    def _read_json(self, filepath, missing=None, label="json"):
        if not os.path.exists(filepath):
            return missing
        try:
            with open(filepath, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception as exc:
            self.log(f"[Monitor] Failed to read {label}: {str(exc)}")
            return missing

    def read_feature_list(self):
        data = self._read_json(
            self.paths.feature_list_file,
            missing=None,
            label="feature_list.json",
        )
        return normalize_feature_list(data) if data else data

    def read_missing_info(self):
        return self._read_json(
            self.paths.missing_info_file,
            missing={"missing_items": []},
            label="missing_info.json",
        )

    def read_test_report(self):
        return self._read_json(
            self.paths.test_report_file,
            missing=None,
            label="test_report.json",
        )

    def read_review_report(self):
        return self._read_json(
            self.paths.review_report_file,
            missing=None,
            label="review_report.json",
        )

    def check_skip_possible(self, blocked_task_args):
        """Check whether another pending feature can be processed first."""
        try:
            data = self.read_feature_list()
            if not data:
                return {"can_skip": False}

            features = get_features_from_data(data)

            blocked_id = None
            if blocked_task_args:
                parts = blocked_task_args.strip().split()
                if len(parts) >= 2:
                    try:
                        blocked_id = int(parts[-1])
                    except ValueError:
                        blocked_id = None

            for feature in features:
                if feature.get("status") != "pending":
                    continue
                deps = feature.get("dependencies", [])
                if blocked_id is None or blocked_id not in deps:
                    return {
                        "can_skip": True,
                        "agent": "coder",
                        "args": f"{feature.get('module', 'unknown')} {feature.get('id')}",
                        "next_task": (
                            f"Feature {feature.get('id')}: "
                            f"{feature.get('description', '')[:50]}"
                        ),
                    }

            return {"can_skip": False}
        except Exception as exc:
            self.log(f"[SkipCheck] Error: {str(exc)}")
            return {"can_skip": False}

    def check_missing_info_resolved(self):
        try:
            data = self.read_missing_info()
            items = data.get("missing_items", [])
            return [item for item in items if item.get("status") in ["done", "skip"]]
        except Exception:
            return []

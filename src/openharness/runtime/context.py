"""Runtime context and shared constants."""

from dataclasses import dataclass, field
import os


IDLE_TIMEOUT = 300
MAX_NO_DECISION = 3
PROGRESS_FILENAME = "claude-progress.txt"
FEATURE_LIST_FILENAME = "feature_list.json"
MISSING_INFO_FILENAME = "missing_info.json"
TEST_REPORT_FILENAME = "test_report.json"
REVIEW_REPORT_FILENAME = "review_report.json"
CACHE_FILENAME = "cache.json"
LOG_FILENAME = "dev-log.txt"
CYCLE_LOG_FILENAME = "cycle-log.txt"
REPORTS_DIRNAME = "reports"
VALID_AGENTS = ("coder", "tester", "fixer", "initializer", "reviewer")
ORCHESTRATOR_PROMPT = (
    "Follow your system instructions: read state from .openharness/, decide "
    "next agent, output decision in format '--- ORCHESTRATOR NEXT: [AGENT] "
    "[args] ---', exit cleanly."
)


@dataclass
class RuntimePaths:
    project_dir: str
    openharness_dir: str = field(init=False)
    active_change_file: str = field(init=False)
    runtime_input_dir: str = field(init=False)
    log_file: str = field(init=False)
    progress_file: str = field(init=False)
    feature_list_file: str = field(init=False)
    missing_info_file: str = field(init=False)
    test_report_file: str = field(init=False)
    review_report_file: str = field(init=False)
    cache_file: str = field(init=False)

    def __post_init__(self):
        self.openharness_dir = os.path.join(self.project_dir, ".openharness")
        self.active_change_file = os.path.join(self.openharness_dir, "active_change")
        self.runtime_input_dir = os.path.join(self.openharness_dir, "runtime-input")
        self.log_file = os.path.join(self.project_dir, LOG_FILENAME)
        self.progress_file = os.path.join(self.openharness_dir, PROGRESS_FILENAME)
        self.feature_list_file = os.path.join(self.openharness_dir, FEATURE_LIST_FILENAME)
        self.missing_info_file = os.path.join(self.openharness_dir, MISSING_INFO_FILENAME)
        self.test_report_file = os.path.join(self.openharness_dir, TEST_REPORT_FILENAME)
        self.review_report_file = os.path.join(self.openharness_dir, REVIEW_REPORT_FILENAME)
        self.cache_file = os.path.join(self.openharness_dir, CACHE_FILENAME)


@dataclass
class RuntimeContext:
    project_dir: str = field(default_factory=os.getcwd)
    idle_timeout: int = IDLE_TIMEOUT
    selected_model: str = None
    current_backend: object = None
    project_id: str = None
    metrics: object = None
    knowledge_mgr: object = None
    last_feature_list: object = None
    paths: RuntimePaths = field(init=False)

    def __post_init__(self):
        self.paths = RuntimePaths(self.project_dir)

    def refresh_paths(self):
        self.paths = RuntimePaths(self.project_dir)

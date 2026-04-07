import json
from pathlib import Path

from openharness.generator.changes import set_active_change
from openharness.monitor import build_monitor_snapshot
from openharness.runtime.context import RuntimeContext


def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def test_build_monitor_snapshot_reads_current_phase_and_progress(tmp_path):
    runtime = RuntimeContext(project_dir=str(tmp_path))
    Path(runtime.paths.openharness_dir).mkdir(parents=True, exist_ok=True)
    set_active_change(str(tmp_path), 'login')

    change_dir = tmp_path / 'input' / 'changes' / 'login'
    change_dir.mkdir(parents=True, exist_ok=True)
    (change_dir / 'meta.yaml').write_text(
        'change_id: login\n'
        'title: Login flow\n'
        'status: draft\n'
        'created_at: 2026-01-01T10:00:00\n',
        encoding='utf-8',
    )

    (tmp_path / 'dev-log.txt').write_text(
        '[2026-01-01 10:00:00] ===== openHarness Started =====\n'
        '[2026-01-01 10:00:01] ===== Cycle 3 =====\n'
        '[2026-01-01 10:00:02] Executing: tester login 3\n',
        encoding='utf-8',
    )
    (Path(runtime.paths.openharness_dir) / 'cycle-log.txt').write_text(
        '\n' + '=' * 80 + '\n'
        'Cycle: 3\n'
        'Time: 2026-01-01 10:00:02\n'
        'Agent: tester\n'
        'Args: login 3\n'
        'Duration: 4.20s\n'
        'Status: success\n'
        'Output Summary:\nRan tests\n'
        + '=' * 80 + '\n',
        encoding='utf-8',
    )
    write_json(
        Path(runtime.paths.feature_list_file),
        {'features': [{'id': 1, 'status': 'completed'}, {'id': 2, 'status': 'pending'}]},
    )
    write_json(Path(runtime.paths.test_report_file), {'overall': 'pass'})
    write_json(Path(runtime.paths.review_report_file), {'overall': 'pending'})
    write_json(Path(runtime.paths.missing_info_file), {'missing_items': []})

    snapshot = build_monitor_snapshot(str(tmp_path))

    assert snapshot['active_change'] == 'login'
    assert snapshot['active_change_title'] == 'Login flow'
    assert snapshot['current_phase'] == 'Tester'
    assert snapshot['current_agent'] == 'tester'
    assert snapshot['current_cycle'] == '3'
    assert snapshot['progress'] == {'total': 2, 'passing': 1, 'percent': 50.0}
    assert snapshot['overall_test_status'] == 'pass'
    assert len(snapshot['timeline']['items']) == 1


def test_build_monitor_snapshot_marks_paused_when_blockers_pending(tmp_path):
    runtime = RuntimeContext(project_dir=str(tmp_path))
    Path(runtime.paths.openharness_dir).mkdir(parents=True, exist_ok=True)

    (tmp_path / 'dev-log.txt').write_text(
        '[2026-01-01 10:00:00] ORCHESTRATOR PAUSED. Check .openharness/missing_info.json\n',
        encoding='utf-8',
    )
    write_json(
        Path(runtime.paths.missing_info_file),
        {'missing_items': [{'id': 'LOGIN_INFO', 'status': 'pending', 'desc': 'Need login rules'}]},
    )

    snapshot = build_monitor_snapshot(str(tmp_path))

    assert snapshot['current_phase'] == 'Paused'
    assert snapshot['pending_blockers'] == 1
    assert snapshot['blockers']['items'][0]['id'] == 'LOGIN_INFO'

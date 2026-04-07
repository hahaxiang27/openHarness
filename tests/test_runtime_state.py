from openharness.runtime.state import (
    get_changes,
    get_progress,
    is_false_completion,
    normalize_feature_list,
    normalize_feature_status,
    parse_agent_output_status,
    parse_orchestrator_decision,
    update_same_decision_state,
)


def test_parse_orchestrator_decision():
    output = 'x\n--- ORCHESTRATOR NEXT: CODER auth 5 ---\n'
    assert parse_orchestrator_decision(output) == ('coder', 'auth 5')


def test_parse_agent_output_status():
    output = '--- AGENT COMPLETE: tester - pass - mapping ---'
    assert parse_agent_output_status(output) == {
        'agent': 'tester',
        'status': 'pass',
        'module': 'mapping',
    }


def test_normalize_feature_status_and_list():
    assert normalize_feature_status('Done') == 'completed'
    data = {'features': [{'id': 1, 'status': 'Finish'}, {'id': 2, 'status': 'pending'}]}
    normalized = normalize_feature_list(data)
    assert normalized['features'][0]['status'] == 'completed'
    assert normalized['features'][1]['status'] == 'pending'


def test_get_progress_and_changes():
    old = {'features': [{'id': 1, 'status': 'pending', 'name': 'A'}]}
    new = {'features': [{'id': 1, 'status': 'completed', 'name': 'A'}]}
    assert get_progress(new) == {'total': 1, 'passing': 1, 'percent': 100.0}
    assert get_changes(old, new) == ['[PASS] 1: A']


def test_false_completion_detection():
    feature_data = {'features': [{'id': 1, 'status': 'completed'}, {'id': 2, 'status': 'pending'}]}
    is_false, details = is_false_completion(feature_data)
    assert is_false is True
    assert details['reason'] == 'pending_features'
    assert details['pending_ids'] == [2]

    is_false, details = is_false_completion(
        {'features': [{'id': 1, 'status': 'completed'}]},
        {'overall': 'fail'},
        None,
    )
    assert is_false is True
    assert details['reason'] == 'test_report_failed'


def test_update_same_decision_state():
    last, count = update_same_decision_state(None, 'coder|auth 1', 0)
    assert (last, count) == ('coder|auth 1', 1)

    last, count = update_same_decision_state(last, 'coder|auth 1', count)
    assert (last, count) == ('coder|auth 1', 2)

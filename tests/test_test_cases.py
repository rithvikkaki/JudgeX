"""Test-case visibility.

The original implementation served every hidden input and expected output from
an unauthenticated endpoint, which gave away the answer key for every problem.
These tests pin the fix.
"""

from tests.conftest import API


def test_hidden_cases_are_redacted_for_anonymous_callers(client, problem_id):
    response = client.get(f"{API}/testcases/problem/{problem_id}")
    assert response.status_code == 200

    hidden = [tc for tc in response.json() if not tc["is_sample"]]
    assert len(hidden) == 2
    for case in hidden:
        assert case["input_data"] is None
        assert case["expected_output"] is None


def test_hidden_cases_are_redacted_for_ordinary_users(
    client, user_headers, problem_id
):
    response = client.get(
        f"{API}/testcases/problem/{problem_id}", headers=user_headers
    )
    hidden = [tc for tc in response.json() if not tc["is_sample"]]
    assert all(case["expected_output"] is None for case in hidden)
    # The hidden expected values must not appear anywhere in the payload.
    assert "30" not in response.text


def test_samples_remain_visible(client, problem_id):
    response = client.get(f"{API}/testcases/problem/{problem_id}")
    samples = [tc for tc in response.json() if tc["is_sample"]]
    assert len(samples) == 1
    assert samples[0]["input_data"] == "2 3"
    assert samples[0]["expected_output"] == "5"


def test_admin_endpoint_returns_everything(client, admin_headers, problem_id):
    response = client.get(
        f"{API}/testcases/problem/{problem_id}/admin", headers=admin_headers
    )
    assert response.status_code == 200
    assert len(response.json()) == 3
    assert all(case["expected_output"] for case in response.json())


def test_admin_endpoint_is_closed_to_ordinary_users(client, user_headers, problem_id):
    response = client.get(
        f"{API}/testcases/problem/{problem_id}/admin", headers=user_headers
    )
    assert response.status_code == 403


def test_only_admins_may_write_test_cases(client, user_headers, problem_id):
    response = client.post(
        f"{API}/testcases/problem/{problem_id}",
        headers=user_headers,
        json={"input_data": "1 1", "expected_output": "2"},
    )
    assert response.status_code == 403


def test_bulk_upload_can_replace_the_suite(client, admin_headers, problem_id):
    response = client.post(
        f"{API}/testcases/problem/{problem_id}/bulk",
        headers=admin_headers,
        json={
            "test_cases": [{"input_data": "1 1", "expected_output": "2"}],
            "replace_existing": True,
        },
    )
    assert response.status_code == 201
    remaining = client.get(
        f"{API}/testcases/problem/{problem_id}/admin", headers=admin_headers
    ).json()
    assert len(remaining) == 1


def test_deleting_a_problem_cascades_to_its_test_cases(
    client, admin_headers, problem_id
):
    assert client.delete(f"{API}/problems/{problem_id}", headers=admin_headers).status_code == 200
    assert client.get(f"{API}/testcases/problem/{problem_id}").status_code == 404

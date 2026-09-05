from tests.conftest import API, judge_submission_record


def test_anonymous_cannot_create_a_problem(client):
    assert client.post(f"{API}/problems", json={}).status_code == 401


def test_non_admin_cannot_create_a_problem(client, user_headers):
    response = client.post(
        f"{API}/problems",
        headers=user_headers,
        json={
            "title": "Nope",
            "description": "should not be created",
            "difficulty": "Easy",
            "input_format": "-",
            "output_format": "-",
            "constraints": "-",
            "sample_input": "-",
            "sample_output": "-",
        },
    )
    assert response.status_code == 403


def test_listing_is_paginated_and_filterable(client, admin_headers, problem_id):
    response = client.get(f"{API}/problems", params={"difficulty": "Easy"})
    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == problem_id

    assert client.get(f"{API}/problems", params={"difficulty": "Hard"}).json()["total"] == 0
    assert client.get(f"{API}/problems", params={"search": "Sum"}).json()["total"] == 1
    assert client.get(f"{API}/problems", params={"search": "zzz"}).json()["total"] == 0


def test_problem_is_addressable_by_slug(client, problem_id):
    response = client.get(f"{API}/problems/sum-of-two-numbers")
    assert response.status_code == 200
    assert response.json()["id"] == problem_id


def test_unpublished_problems_are_hidden_from_non_admins(
    client, admin_headers, problem_id
):
    client.patch(
        f"{API}/problems/{problem_id}", headers=admin_headers, json={"is_public": False}
    )
    # 404, not 403: an unpublished problem should not even be discoverable.
    assert client.get(f"{API}/problems/{problem_id}").status_code == 404
    assert client.get(f"{API}/problems").json()["total"] == 0
    assert (
        client.get(f"{API}/problems/{problem_id}", headers=admin_headers).status_code
        == 200
    )


def test_patch_only_touches_supplied_fields(client, admin_headers, problem_id):
    before = client.get(f"{API}/problems/{problem_id}").json()
    response = client.patch(
        f"{API}/problems/{problem_id}",
        headers=admin_headers,
        json={"difficulty": "Hard"},
    )
    assert response.status_code == 200
    after = response.json()
    assert after["difficulty"] == "Hard"
    assert after["description"] == before["description"]
    assert after["title"] == before["title"]


def test_duplicate_titles_are_rejected(client, admin_headers, problem_id):
    response = client.post(
        f"{API}/problems",
        headers=admin_headers,
        json={
            "title": "Sum of Two Numbers",
            "description": "a duplicate title",
            "difficulty": "Easy",
            "input_format": "-",
            "output_format": "-",
            "constraints": "-",
            "sample_input": "-",
            "sample_output": "-",
        },
    )
    assert response.status_code == 409


def test_solved_flag_reflects_the_caller(client, user_headers, problem_id):
    anonymous = client.get(f"{API}/problems/{problem_id}").json()
    assert anonymous["solved_by_me"] is None

    response = client.post(
        f"{API}/submissions",
        headers=user_headers,
        json={
            "problem_id": problem_id,
            "language": "python",
            "source_code": "a, b = map(int, input().split())\nprint(a + b)\n",
        },
    )
    assert response.status_code == 202, response.text
    judge_submission_record(response.json()["id"])
    mine = client.get(f"{API}/problems/{problem_id}", headers=user_headers).json()
    assert mine["solved_by_me"] is True
    assert mine["attempted_by_me"] is True
    assert mine["accepted_submissions"] == 1

from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import API, SOLUTION_ACCEPTED, SOLUTION_WRONG, judge_submission_record


def make_contest(client, headers, *, starts_in=-10, ends_in=120, title="Weekly Round 1"):
    now = datetime.now(timezone.utc)
    response = client.post(
        f"{API}/contests",
        headers=headers,
        json={
            "title": title,
            "description": "An automated test contest",
            "start_time": (now + timedelta(minutes=starts_in)).isoformat(),
            "end_time": (now + timedelta(minutes=ends_in)).isoformat(),
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.fixture
def running_contest(client, admin_headers, problem_id):
    contest = make_contest(client, admin_headers)
    client.post(
        f"{API}/contests/{contest['id']}/problems",
        headers=admin_headers,
        json={"problem_id": problem_id, "points": 100},
    )
    return contest


def test_only_admins_may_create_contests(client, user_headers):
    now = datetime.now(timezone.utc)
    response = client.post(
        f"{API}/contests",
        headers=user_headers,
        json={
            "title": "Sneaky",
            "description": "nope",
            "start_time": now.isoformat(),
            "end_time": (now + timedelta(hours=1)).isoformat(),
        },
    )
    assert response.status_code == 403


def test_end_time_must_follow_start_time(client, admin_headers):
    now = datetime.now(timezone.utc)
    response = client.post(
        f"{API}/contests",
        headers=admin_headers,
        json={
            "title": "Backwards",
            "description": "invalid window",
            "start_time": now.isoformat(),
            "end_time": (now - timedelta(hours=1)).isoformat(),
        },
    )
    assert response.status_code == 422


def test_state_is_derived_from_the_window(client, admin_headers):
    assert make_contest(client, admin_headers, starts_in=-10, ends_in=60)["state"] == "Running"
    assert (
        make_contest(client, admin_headers, starts_in=60, ends_in=120, title="Future")["state"]
        == "Upcoming"
    )
    assert (
        make_contest(client, admin_headers, starts_in=-120, ends_in=-60, title="Past")["state"]
        == "Ended"
    )


def test_upcoming_contest_problems_are_withheld(client, admin_headers, problem_id):
    contest = make_contest(client, admin_headers, starts_in=60, ends_in=120, title="Future")
    client.post(
        f"{API}/contests/{contest['id']}/problems",
        headers=admin_headers,
        json={"problem_id": problem_id},
    )
    # A participant must not be able to read the questions before the start.
    assert client.get(f"{API}/contests/{contest['id']}/problems").status_code == 409
    assert (
        client.get(
            f"{API}/contests/{contest['id']}/problems", headers=admin_headers
        ).status_code
        == 200
    )


def test_joining_twice_is_rejected(client, user_headers, running_contest):
    cid = running_contest["id"]
    assert client.post(f"{API}/contests/{cid}/join", headers=user_headers).status_code == 201
    assert client.post(f"{API}/contests/{cid}/join", headers=user_headers).status_code == 409


def test_a_problem_cannot_be_added_twice(client, admin_headers, running_contest, problem_id):
    response = client.post(
        f"{API}/contests/{running_contest['id']}/problems",
        headers=admin_headers,
        json={"problem_id": problem_id},
    )
    assert response.status_code == 409


def test_contest_submission_requires_registration(
    client, user_headers, running_contest, problem_id
):
    response = client.post(
        f"{API}/submissions",
        headers=user_headers,
        json={
            "problem_id": problem_id,
            "language": "python",
            "source_code": SOLUTION_ACCEPTED,
            "contest_id": running_contest["id"],
        },
    )
    assert response.status_code == 403


def test_cannot_join_a_contest_that_already_ended(client, admin_headers, user_headers):
    contest = make_contest(client, admin_headers, starts_in=-120, ends_in=-60, title="Past")
    response = client.post(f"{API}/contests/{contest['id']}/join", headers=user_headers)
    assert response.status_code == 409


def test_cannot_submit_after_the_contest_ends(
    client, admin_headers, user_headers, running_contest, problem_id
):
    cid = running_contest["id"]
    client.post(f"{API}/contests/{cid}/join", headers=user_headers)

    # Wind the window into the past, as if the clock had run out on a
    # participant who joined while the contest was live.
    now = datetime.now(timezone.utc)
    client.patch(
        f"{API}/contests/{cid}",
        headers=admin_headers,
        json={
            "start_time": (now - timedelta(minutes=120)).isoformat(),
            "end_time": (now - timedelta(minutes=60)).isoformat(),
        },
    )

    response = client.post(
        f"{API}/submissions",
        headers=user_headers,
        json={
            "problem_id": problem_id,
            "language": "python",
            "source_code": SOLUTION_ACCEPTED,
            "contest_id": cid,
        },
    )
    assert response.status_code == 409
    assert "ended" in response.json()["detail"].lower()


def test_cannot_submit_before_the_contest_starts(
    client, admin_headers, user_headers, problem_id
):
    contest = make_contest(client, admin_headers, starts_in=60, ends_in=120, title="Future")
    client.post(
        f"{API}/contests/{contest['id']}/problems",
        headers=admin_headers,
        json={"problem_id": problem_id},
    )
    client.post(f"{API}/contests/{contest['id']}/join", headers=user_headers)

    response = client.post(
        f"{API}/submissions",
        headers=user_headers,
        json={
            "problem_id": problem_id,
            "language": "python",
            "source_code": SOLUTION_ACCEPTED,
            "contest_id": contest["id"],
        },
    )
    assert response.status_code == 409
    assert "not started" in response.json()["detail"].lower()


class TestLeaderboard:
    """Scoring rules that the previous implementation got wrong."""

    def _submit(self, client, headers, problem_id, source, contest_id):
        response = client.post(
            f"{API}/submissions",
            headers=headers,
            json={
                "problem_id": problem_id,
                "language": "python",
                "source_code": source,
                "contest_id": contest_id,
            },
        )
        if response.status_code == 202:
            judge_submission_record(response.json()["id"])
        return response

    def test_resubmitting_an_accepted_problem_earns_nothing_extra(
        self, client, user_headers, running_contest, problem_id
    ):
        cid = running_contest["id"]
        client.post(f"{API}/contests/{cid}/join", headers=user_headers)

        for _ in range(3):
            self._submit(client, user_headers, problem_id, SOLUTION_ACCEPTED, cid)

        entry = client.get(f"{API}/contests/{cid}/leaderboard").json()["entries"][0]
        assert entry["score"] == 100
        assert entry["solved"] == 1
        # Only the attempt up to and including the solve is counted.
        assert entry["problems"][0]["attempts"] == 1

    def test_practice_submissions_do_not_affect_standings(
        self, client, user_headers, running_contest, problem_id
    ):
        cid = running_contest["id"]
        client.post(f"{API}/contests/{cid}/join", headers=user_headers)

        # No contest_id: a practice submission.
        response = client.post(
            f"{API}/submissions",
            headers=user_headers,
            json={
                "problem_id": problem_id,
                "language": "python",
                "source_code": SOLUTION_ACCEPTED,
            },
        )
        assert response.status_code == 202, response.text
        judge_submission_record(response.json()["id"])

        entry = client.get(f"{API}/contests/{cid}/leaderboard").json()["entries"][0]
        assert entry["score"] == 0
        assert entry["solved"] == 0

    def test_wrong_attempts_add_penalty_only_when_solved(
        self, client, admin_headers, user_headers, running_contest, problem_id
    ):
        cid = running_contest["id"]
        client.post(f"{API}/contests/{cid}/join", headers=user_headers)

        rival = client.post(
            f"{API}/auth/register",
            json={
                "username": "rival",
                "email": "rival@example.com",
                "password": "rivalPass123",
            },
        ).json()
        rival_headers = {"Authorization": f"Bearer {rival['access_token']}"}
        client.post(f"{API}/contests/{cid}/join", headers=rival_headers)

        # alice fails once before solving; rival solves first time.
        self._submit(client, user_headers, problem_id, SOLUTION_WRONG, cid)
        self._submit(client, user_headers, problem_id, SOLUTION_ACCEPTED, cid)
        self._submit(client, rival_headers, problem_id, SOLUTION_ACCEPTED, cid)

        board = client.get(f"{API}/contests/{cid}/leaderboard").json()
        by_name = {e["username"]: e for e in board["entries"]}

        assert by_name["alice"]["score"] == by_name["rival"]["score"] == 100
        # Equal score, so the penalty breaks the tie in rival's favour.
        assert by_name["alice"]["penalty"] > by_name["rival"]["penalty"]
        assert by_name["rival"]["rank"] == 1
        assert by_name["alice"]["rank"] == 2

    def test_registered_user_with_no_submissions_still_appears(
        self, client, user_headers, running_contest
    ):
        cid = running_contest["id"]
        client.post(f"{API}/contests/{cid}/join", headers=user_headers)

        board = client.get(f"{API}/contests/{cid}/leaderboard").json()
        assert board["total_participants"] == 1
        assert board["entries"][0]["score"] == 0

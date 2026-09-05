"""Populate the database with an admin account, problems and a live contest.

Run it against any configured database:

    python -m scripts.seed                 # keep anything already present
    python -m scripts.seed --reset         # drop and recreate every table first

The script is idempotent: re-running it will not duplicate rows.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import SessionLocal, engine  # noqa: E402
from app.models import (  # noqa: E402
    Base,
    Contest,
    ContestProblem,
    Problem,
    TestCase,
    User,
)
from app.utils.security import hash_password  # noqa: E402
from app.utils.slug import unique_slug  # noqa: E402

DEFAULT_ADMIN_EMAIL = "admin@example.com"

# The seeded passwords are published in this repository, so they are only safe
# as local development defaults. Override them via the environment before
# seeding anything reachable from the internet:
#
#     SEED_ADMIN_PASSWORD=... SEED_DEMO_PASSWORD=... python -m scripts.seed
#
# To change the password of an account that already exists, use
# `python scripts/set_password.py` instead - re-seeding would drop your data.
DEFAULT_ADMIN_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "AdminPass123")
DEFAULT_DEMO_PASSWORD = os.getenv("SEED_DEMO_PASSWORD", "DemoPass123")


PROBLEMS: list[dict] = [
    {
        "title": "Sum of Two Numbers",
        "difficulty": "Easy",
        "description": (
            "Given two integers **a** and **b**, print their sum.\n\n"
            "This is the classic warm-up problem: it checks that you can read "
            "from standard input and write to standard output."
        ),
        "input_format": "A single line containing two space-separated integers a and b.",
        "output_format": "A single integer: the value of a + b.",
        "constraints": "-10^9 <= a, b <= 10^9",
        "sample_input": "2 3",
        "sample_output": "5",
        "time_limit_ms": 2000,
        "tests": [
            ("2 3", "5", True),
            ("10 20", "30", True),
            ("-5 5", "0", False),
            ("1000000000 1000000000", "2000000000", False),
            ("-1000000000 -1000000000", "-2000000000", False),
            ("0 0", "0", False),
        ],
    },
    {
        "title": "Reverse a String",
        "difficulty": "Easy",
        "description": (
            "Read a single line of text and print it reversed.\n\n"
            "The input contains no leading or trailing spaces."
        ),
        "input_format": "A single line containing a string s.",
        "output_format": "The reverse of s.",
        "constraints": "1 <= |s| <= 10^5, s consists of printable ASCII characters.",
        "sample_input": "hello",
        "sample_output": "olleh",
        "time_limit_ms": 2000,
        "tests": [
            ("hello", "olleh", True),
            ("a", "a", True),
            ("racecar", "racecar", False),
            ("OnlineJudge", "egduJenilnO", False),
            ("12345", "54321", False),
        ],
    },
    {
        "title": "FizzBuzz",
        "difficulty": "Easy",
        "description": (
            "For every integer i from 1 to n, print:\n\n"
            "- `FizzBuzz` if i is divisible by both 3 and 5\n"
            "- `Fizz` if i is divisible by 3\n"
            "- `Buzz` if i is divisible by 5\n"
            "- otherwise the number itself\n\n"
            "Print one value per line."
        ),
        "input_format": "A single integer n.",
        "output_format": "n lines, following the rules above.",
        "constraints": "1 <= n <= 10^4",
        "sample_input": "5",
        "sample_output": "1\n2\nFizz\n4\nBuzz",
        "time_limit_ms": 2000,
        "tests": [
            ("5", "1\n2\nFizz\n4\nBuzz", True),
            ("3", "1\n2\nFizz", True),
            ("15", "1\n2\nFizz\n4\nBuzz\nFizz\n7\n8\nFizz\nBuzz\n11\nFizz\n13\n14\nFizzBuzz", False),
            ("1", "1", False),
        ],
    },
    {
        "title": "Maximum Subarray Sum",
        "difficulty": "Medium",
        "description": (
            "Given an array of n integers, find the largest sum obtainable "
            "from any contiguous non-empty subarray.\n\n"
            "A linear solution (Kadane's algorithm) comfortably fits the limits."
        ),
        "input_format": (
            "The first line contains n. The second line contains n "
            "space-separated integers."
        ),
        "output_format": "A single integer: the maximum subarray sum.",
        "constraints": "1 <= n <= 10^5, -10^4 <= a[i] <= 10^4",
        "sample_input": "9\n-2 1 -3 4 -1 2 1 -5 4",
        "sample_output": "6",
        "time_limit_ms": 3000,
        "tests": [
            ("9\n-2 1 -3 4 -1 2 1 -5 4", "6", True),
            ("1\n-5", "-5", True),
            ("5\n1 2 3 4 5", "15", False),
            ("5\n-1 -2 -3 -4 -5", "-1", False),
            ("8\n5 4 -1 7 8 -20 100 -1", "103", False),
        ],
    },
    {
        "title": "Count Primes Below N",
        "difficulty": "Medium",
        "description": (
            "Count how many prime numbers are strictly less than n.\n\n"
            "A sieve of Eratosthenes is the intended approach; trial division "
            "will exceed the time limit on the larger tests."
        ),
        "input_format": "A single integer n.",
        "output_format": "The count of primes p with p < n.",
        "constraints": "0 <= n <= 10^6",
        "sample_input": "10",
        "sample_output": "4",
        "time_limit_ms": 4000,
        "tests": [
            ("10", "4", True),
            ("2", "0", True),
            ("0", "0", False),
            ("100", "25", False),
            ("1000", "168", False),
            ("100000", "9592", False),
        ],
    },
    {
        "title": "Longest Common Subsequence",
        "difficulty": "Hard",
        "description": (
            "Given two strings, find the length of their longest common "
            "subsequence.\n\n"
            "A subsequence keeps the relative order of characters but need not "
            "be contiguous."
        ),
        "input_format": "Two lines, each containing one string.",
        "output_format": "A single integer: the length of the LCS.",
        "constraints": "1 <= |a|, |b| <= 1000, lowercase English letters.",
        "sample_input": "abcde\nace",
        "sample_output": "3",
        "time_limit_ms": 5000,
        "tests": [
            ("abcde\nace", "3", True),
            ("abc\nabc", "3", True),
            ("abc\ndef", "0", False),
            ("aggtab\ngxtxayb", "4", False),
            ("bsbininm\njmjkbkjkv", "1", False),
        ],
    },
]


def seed(reset: bool = False) -> None:
    if reset:
        print("Dropping every table ...")
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        admin = _seed_admin(db)
        _seed_demo_user(db)
        problems = _seed_problems(db)
        _seed_contest(db, admin, problems)
        db.commit()

    _print_summary()


def _seed_admin(db) -> User:
    email = next(iter(settings.admin_email_set), DEFAULT_ADMIN_EMAIL)

    admin = db.scalar(select(User).where(User.email == email))
    if admin is not None:
        # Ensure the account really is an admin even if it predates the setting.
        if not admin.is_admin:
            admin.is_admin = True
            print(f"Promoted existing user {email} to admin")
        else:
            print(f"Admin {email} already present")
        return admin

    admin = User(
        username="admin",
        email=email,
        hashed_password=hash_password(DEFAULT_ADMIN_PASSWORD),
        is_admin=True,
    )
    db.add(admin)
    db.flush()
    print(f"Created admin {email}")
    return admin


def _seed_demo_user(db) -> User:
    email = "demo@example.com"
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user

    user = User(
        username="demo",
        email=email,
        hashed_password=hash_password(DEFAULT_DEMO_PASSWORD),
    )
    db.add(user)
    db.flush()
    print(f"Created demo user {email}")
    return user


def _seed_problems(db) -> list[Problem]:
    created: list[Problem] = []

    for spec in PROBLEMS:
        existing = db.scalar(select(Problem).where(Problem.title == spec["title"]))
        if existing is not None:
            created.append(existing)
            continue

        problem = Problem(
            title=spec["title"],
            slug=unique_slug(
                spec["title"],
                lambda s: db.scalar(select(Problem.id).where(Problem.slug == s))
                is not None,
            ),
            description=spec["description"],
            difficulty=spec["difficulty"],
            input_format=spec["input_format"],
            output_format=spec["output_format"],
            constraints=spec["constraints"],
            sample_input=spec["sample_input"],
            sample_output=spec["sample_output"],
            time_limit_ms=spec.get("time_limit_ms", 2000),
            memory_limit_mb=spec.get("memory_limit_mb", 128),
        )
        db.add(problem)
        db.flush()

        for index, (stdin, expected, is_sample) in enumerate(spec["tests"]):
            db.add(
                TestCase(
                    problem_id=problem.id,
                    input_data=stdin,
                    expected_output=expected,
                    is_sample=is_sample,
                    order_index=index,
                )
            )

        created.append(problem)
        samples = sum(1 for t in spec["tests"] if t[2])
        print(
            f"Created problem {problem.title!r} "
            f"({samples} sample, {len(spec['tests']) - samples} hidden tests)"
        )

    return created


def _seed_contest(db, admin: User, problems: list[Problem]) -> None:
    title = "Practice Round #1"
    if db.scalar(select(Contest).where(Contest.title == title)) is not None:
        print("Contest already present")
        return

    now = datetime.now(timezone.utc)
    contest = Contest(
        title=title,
        slug=unique_slug(
            title,
            lambda s: db.scalar(select(Contest.id).where(Contest.slug == s)) is not None,
        ),
        description=(
            "An always-open practice contest seeded for the demo. It starts an "
            "hour in the past and runs for a year, so you can join and submit "
            "at any time."
        ),
        # A window that is already open, so the demo is immediately usable.
        start_time=now - timedelta(hours=1),
        end_time=now + timedelta(days=365),
        penalty_minutes_per_wrong=20,
        created_by=admin.id,
    )
    db.add(contest)
    db.flush()

    for index, problem in enumerate(problems[:4]):
        db.add(
            ContestProblem(
                contest_id=contest.id,
                problem_id=problem.id,
                label=chr(ord("A") + index),
                points=100 * (index + 1),
                order_index=index,
            )
        )

    print(f"Created contest {title!r} with {min(len(problems), 4)} problems")


def _print_summary() -> None:
    admin_email = next(iter(settings.admin_email_set), DEFAULT_ADMIN_EMAIL)
    print(
        "\n"
        "-------------------------------------------------------------\n"
        " Seed complete.\n"
        "\n"
        f"   Admin : {admin_email} / {DEFAULT_ADMIN_PASSWORD}\n"
        f"   Demo  : demo@example.com / {DEFAULT_DEMO_PASSWORD}\n"
        "\n"
        " Change these before exposing the deployment publicly.\n"
        "-------------------------------------------------------------"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the judge database")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="drop every table before seeding (destroys all data)",
    )
    args = parser.parse_args()
    seed(reset=args.reset)

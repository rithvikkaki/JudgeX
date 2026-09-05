"""Judge a reference solution against every seeded problem.

Run this after ``scripts.seed`` to confirm the bundled test data is
self-consistent: if a seeded expected output is wrong, a known-correct
solution fails here rather than confusing the first user who tries it.

    python -m scripts.seed --reset
    python scripts/verify_seed.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

API = "/api/v1"

#: A known-correct Python solution per seeded problem title.
REFERENCE_SOLUTIONS: dict[str, str] = {
    "Sum of Two Numbers": "a, b = map(int, input().split())\nprint(a + b)\n",
    "Reverse a String": "print(input()[::-1])\n",
    "FizzBuzz": (
        "n = int(input())\n"
        "for i in range(1, n + 1):\n"
        "    if i % 15 == 0:\n"
        "        print('FizzBuzz')\n"
        "    elif i % 3 == 0:\n"
        "        print('Fizz')\n"
        "    elif i % 5 == 0:\n"
        "        print('Buzz')\n"
        "    else:\n"
        "        print(i)\n"
    ),
    "Maximum Subarray Sum": (
        "input()\n"
        "values = list(map(int, input().split()))\n"
        "best = current = values[0]\n"
        "for value in values[1:]:\n"
        "    current = max(value, current + value)\n"
        "    best = max(best, current)\n"
        "print(best)\n"
    ),
    "Count Primes Below N": (
        "n = int(input())\n"
        "if n < 3:\n"
        "    print(0)\n"
        "else:\n"
        "    sieve = bytearray([1]) * n\n"
        "    sieve[0] = sieve[1] = 0\n"
        "    i = 2\n"
        "    while i * i < n:\n"
        "        if sieve[i]:\n"
        "            sieve[i * i::i] = bytearray(len(sieve[i * i::i]))\n"
        "        i += 1\n"
        "    print(sum(sieve))\n"
    ),
    "Longest Common Subsequence": (
        "a = input()\n"
        "b = input()\n"
        "previous = [0] * (len(b) + 1)\n"
        "for x in a:\n"
        "    current = [0] * (len(b) + 1)\n"
        "    for j, y in enumerate(b, 1):\n"
        "        current[j] = previous[j - 1] + 1 if x == y else max(previous[j], current[j - 1])\n"
        "    previous = current\n"
        "print(previous[-1])\n"
    ),
}


def main() -> int:
    client = TestClient(app)

    login = client.post(
        f"{API}/auth/login",
        json={"email": "demo@example.com", "password": "DemoPass123"},
    )
    if login.status_code != 200:
        print("Could not sign in as the demo user. Run `python -m scripts.seed` first.")
        return 1

    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    problems = client.get(f"{API}/problems", params={"limit": 100}).json()["items"]

    if not problems:
        print("No problems found. Run `python -m scripts.seed` first.")
        return 1

    failures: list[str] = []
    print(f"Verifying {len(problems)} seeded problems\n")

    for problem in problems:
        solution = REFERENCE_SOLUTIONS.get(problem["title"])
        if solution is None:
            print(f"  SKIP {problem['title']} (no reference solution)")
            continue

        response = client.post(
            f"{API}/submissions",
            headers=headers,
            json={
                "problem_id": problem["id"],
                "language": "python",
                "source_code": solution,
            },
        )
        body = response.json()
        verdict = body.get("verdict")
        accepted = verdict == "Accepted"

        print(
            f"  {'OK  ' if accepted else 'FAIL'} {problem['title']:<32} "
            f"{verdict:<22} {body.get('passed_tests')}/{body.get('total_tests')} tests "
            f"{body.get('execution_time_ms')} ms"
        )

        if not accepted:
            failures.append(
                f"{problem['title']}: {verdict} "
                f"(test #{body.get('failed_test_index')}) {body.get('error_message') or ''}"
            )

    if failures:
        print("\nFAILED:")
        for failure in failures:
            print(f"  - {failure}")
        return 1

    print("\nAll seeded problems accept their reference solution.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

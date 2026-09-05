"""Guards on files that tooling outside Python has to read.

`requirements.txt` has broken two deployments by being saved as UTF-16:
PowerShell's `>` and `Set-Content` default to UTF-16LE, so a single
`pip freeze > requirements.txt` silently corrupts it. pip then reports the
baffling `Invalid requirement: '\\x00f\\x00a\\x00s\\x00t\\x00a\\x00p\\x00i'`
at build time rather than locally. This catches it in CI instead.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

TEXT_FILES = [
    "requirements.txt",
    "Dockerfile",
    ".env.example",
    "render.yaml",
    "docker-compose.yml",
]


@pytest.mark.parametrize("filename", TEXT_FILES)
def test_file_has_no_null_bytes(filename: str):
    path = REPO_ROOT / filename
    if not path.exists():
        pytest.skip(f"{filename} is not present")

    raw = path.read_bytes()
    assert b"\x00" not in raw, (
        f"{filename} contains null bytes, i.e. it was saved as UTF-16. "
        f"Re-save it as UTF-8. In PowerShell use "
        f"`Set-Content -Encoding utf8`, never bare `>`."
    )


@pytest.mark.parametrize("filename", TEXT_FILES)
def test_file_has_no_byte_order_mark(filename: str):
    path = REPO_ROOT / filename
    if not path.exists():
        pytest.skip(f"{filename} is not present")

    raw = path.read_bytes()
    for bom, label in (
        (b"\xef\xbb\xbf", "UTF-8 BOM"),
        (b"\xff\xfe", "UTF-16 LE BOM"),
        (b"\xfe\xff", "UTF-16 BE BOM"),
    ):
        assert not raw.startswith(bom), f"{filename} starts with a {label}"


def test_requirements_are_parseable_and_pinned():
    lines = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8").splitlines()
    requirements = [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]

    assert requirements, "requirements.txt lists no packages"

    for requirement in requirements:
        assert requirement.isascii(), f"non-ASCII characters in {requirement!r}"
        # Every dependency is pinned, so a deployment cannot pick up a
        # different version than the one the tests ran against.
        assert "==" in requirement, f"{requirement!r} is not pinned to a version"


def test_core_dependencies_are_declared():
    text = (REPO_ROOT / "requirements.txt").read_text(encoding="utf-8")
    for package in ("fastapi", "uvicorn", "SQLAlchemy", "psycopg2-binary", "bcrypt"):
        assert package in text, f"{package} is missing from requirements.txt"

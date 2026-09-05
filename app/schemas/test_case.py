from __future__ import annotations

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class TestCaseCreate(BaseModel):
    input_data: str
    expected_output: str
    is_sample: bool = False
    order_index: int = Field(default=0, ge=0)


class TestCaseBulkCreate(BaseModel):
    """Upload a whole suite in one call - what the seed script uses."""

    test_cases: list[TestCaseCreate] = Field(min_length=1, max_length=200)
    replace_existing: bool = Field(
        default=False,
        description="Delete the problem's current test cases before inserting",
    )


class TestCaseUpdate(BaseModel):
    input_data: str | None = None
    expected_output: str | None = None
    is_sample: bool | None = None
    order_index: int | None = Field(default=None, ge=0)


class TestCaseResponse(ORMModel):
    """Full test case - only ever returned to admins."""

    id: int
    problem_id: int
    input_data: str
    expected_output: str
    is_sample: bool
    order_index: int


class TestCasePublic(ORMModel):
    """What a non-admin may see: samples in full, hidden ones as a stub."""

    id: int
    problem_id: int
    is_sample: bool
    order_index: int
    input_data: str | None = None
    expected_output: str | None = None

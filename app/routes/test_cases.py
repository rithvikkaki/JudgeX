"""Test case management.

The visibility rule is the security-relevant part: **hidden test cases are
never returned to a non-admin.**  The old implementation exposed every hidden
input and expected output on an unauthenticated endpoint, which handed away the
answer key for every problem.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.dependencies.auth import get_current_admin, get_optional_user
from app.dependencies.database import get_db
from app.models.problem import Problem
from app.models.test_case import TestCase
from app.models.user import User
from app.schemas.common import Message
from app.schemas.test_case import (
    TestCaseBulkCreate,
    TestCaseCreate,
    TestCasePublic,
    TestCaseResponse,
    TestCaseUpdate,
)

router = APIRouter(prefix="/testcases", tags=["Test Cases"])


@router.get(
    "/problem/{problem_id}",
    response_model=list[TestCasePublic],
    summary="List a problem's test cases (hidden ones are redacted)",
)
def list_test_cases(
    problem_id: int,
    db: Session = Depends(get_db),
    viewer: User | None = Depends(get_optional_user),
) -> list[TestCasePublic]:
    _require_problem(db, problem_id)
    is_admin = bool(viewer and viewer.is_admin)

    test_cases = list(
        db.scalars(
            select(TestCase)
            .where(TestCase.problem_id == problem_id)
            .order_by(TestCase.is_sample.desc(), TestCase.order_index, TestCase.id)
        )
    )

    results: list[TestCasePublic] = []
    for test_case in test_cases:
        item = TestCasePublic(
            id=test_case.id,
            problem_id=test_case.problem_id,
            is_sample=test_case.is_sample,
            order_index=test_case.order_index,
        )
        # Sample data is already on the problem page, so echoing it is fine.
        # Hidden data stays out of the payload entirely - not blanked client
        # side, simply never serialised.
        if test_case.is_sample or is_admin:
            item.input_data = test_case.input_data
            item.expected_output = test_case.expected_output
        results.append(item)

    return results


@router.get(
    "/problem/{problem_id}/admin",
    response_model=list[TestCaseResponse],
    summary="Full test suite including hidden cases (admin only)",
)
def list_test_cases_admin(
    problem_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> list[TestCase]:
    _require_problem(db, problem_id)
    return list(
        db.scalars(
            select(TestCase)
            .where(TestCase.problem_id == problem_id)
            .order_by(TestCase.is_sample.desc(), TestCase.order_index, TestCase.id)
        )
    )


@router.post(
    "/problem/{problem_id}",
    response_model=TestCaseResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add one test case (admin only)",
)
def create_test_case(
    problem_id: int,
    payload: TestCaseCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> TestCase:
    _require_problem(db, problem_id)

    test_case = TestCase(
        problem_id=problem_id,
        **payload.model_dump(),
    )
    db.add(test_case)
    db.commit()
    db.refresh(test_case)
    return test_case


@router.post(
    "/problem/{problem_id}/bulk",
    response_model=list[TestCaseResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload a whole test suite in one call (admin only)",
)
def bulk_create_test_cases(
    problem_id: int,
    payload: TestCaseBulkCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> list[TestCase]:
    _require_problem(db, problem_id)

    if payload.replace_existing:
        db.execute(delete(TestCase).where(TestCase.problem_id == problem_id))

    next_index = (
        0
        if payload.replace_existing
        else int(
            db.scalar(
                select(func.coalesce(func.max(TestCase.order_index), -1)).where(
                    TestCase.problem_id == problem_id
                )
            )
            or -1
        )
        + 1
    )

    created: list[TestCase] = []
    for offset, item in enumerate(payload.test_cases):
        test_case = TestCase(
            problem_id=problem_id,
            input_data=item.input_data,
            expected_output=item.expected_output,
            is_sample=item.is_sample,
            # Respect an explicit index, otherwise append in upload order.
            order_index=item.order_index or (next_index + offset),
        )
        db.add(test_case)
        created.append(test_case)

    db.commit()
    for test_case in created:
        db.refresh(test_case)

    return created


@router.patch(
    "/{testcase_id}",
    response_model=TestCaseResponse,
    summary="Update a test case (admin only)",
)
def update_test_case(
    testcase_id: int,
    payload: TestCaseUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> TestCase:
    test_case = db.get(TestCase, testcase_id)
    if test_case is None:
        raise _not_found()

    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(test_case, field, value)

    db.commit()
    db.refresh(test_case)
    return test_case


@router.delete(
    "/{testcase_id}", response_model=Message, summary="Delete a test case (admin only)"
)
def delete_test_case(
    testcase_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_current_admin),
) -> Message:
    test_case = db.get(TestCase, testcase_id)
    if test_case is None:
        raise _not_found()

    db.delete(test_case)
    db.commit()
    return Message(message="Test case deleted successfully")


# ---------------------------------------------------------------------- #
def _require_problem(db: Session, problem_id: int) -> Problem:
    problem = db.get(Problem, problem_id)
    if problem is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found"
        )
    return problem


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND, detail="Test case not found"
    )

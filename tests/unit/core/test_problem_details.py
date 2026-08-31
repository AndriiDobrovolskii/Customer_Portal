import pytest

from app.core.exceptions import DomainError
from app.core.problem_details import ProblemError

pytestmark = pytest.mark.unit


class _StubProblemError(ProblemError):
    type_slug = "stub-error"
    title = "Stub Error"
    status = 400
    detail = "A stub error for testing."


def test_problem_error_is_a_domain_error() -> None:
    # Act
    error = _StubProblemError()

    # Assert
    assert isinstance(error, DomainError)
    assert error.type_slug == "stub-error"
    assert error.title == "Stub Error"
    assert error.status == 400
    assert error.detail == "A stub error for testing."
    assert error.headers is None

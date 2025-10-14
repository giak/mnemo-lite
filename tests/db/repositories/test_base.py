"""
Tests for base.py - Base repository exception class.
"""

import pytest
from db.repositories.base import RepositoryError


def test_repository_error_can_be_raised():
    """
    Test that RepositoryError can be raised.

    Verifies basic exception functionality.
    """
    with pytest.raises(RepositoryError):
        raise RepositoryError("Test error")


def test_repository_error_with_message():
    """
    Test that RepositoryError preserves error message.

    Verifies that exception message can be accessed.
    """
    error_message = "Database connection failed"

    try:
        raise RepositoryError(error_message)
    except RepositoryError as e:
        assert str(e) == error_message


def test_repository_error_inheritance():
    """
    Test that RepositoryError inherits from Exception.

    Verifies correct exception hierarchy.
    """
    assert issubclass(RepositoryError, Exception)


def test_repository_error_can_be_caught_as_exception():
    """
    Test that RepositoryError can be caught as generic Exception.

    Verifies that standard exception handling works.
    """
    try:
        raise RepositoryError("Test")
    except Exception as e:
        assert isinstance(e, RepositoryError)
        assert isinstance(e, Exception)


def test_repository_error_with_no_message():
    """
    Test that RepositoryError can be raised without message.

    Verifies default exception behavior.
    """
    with pytest.raises(RepositoryError):
        raise RepositoryError()

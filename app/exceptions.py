"""Errors this application raises on purpose.

Every exception here subclasses HTTPException, so a service can raise one and
FastAPI turns it into the right status code on its own -- no handler wiring in
main.py, and no service that has to know what a status code is.

Subclasses set `_status` and `_detail` rather than `status_code`/`detail`:
those two names belong to the HTTPException instance, and shadowing them with
class attributes makes the resulting object hard to reason about.
"""

from typing import Optional

from fastapi import HTTPException, status


class AppException(HTTPException):
    """Base for every deliberate error. Never raised directly."""

    _status: int = status.HTTP_400_BAD_REQUEST
    _detail: str = "Request could not be completed"

    def __init__(self, detail: Optional[str] = None):
        super().__init__(status_code=self._status, detail=detail or self._detail)


class EntityNotFoundException(AppException):
    _status = status.HTTP_404_NOT_FOUND
    _detail = "Resource not found"


class DuplicateResourceException(AppException):
    _status = status.HTTP_409_CONFLICT
    _detail = "Resource already exists"


class UnauthorizedAccessException(AppException):
    """403, not 401: the caller is authenticated, just not allowed."""

    _status = status.HTTP_403_FORBIDDEN
    _detail = "Not permitted"


class InvalidOperationException(AppException):
    """The request parsed fine but asks for something the data forbids."""

    _status = 422  # Unprocessable Content
    _detail = "Operation not allowed in this state"


class IncompleteProfileException(AppException):
    _status = 422  # Unprocessable Content
    _detail = "Profile is incomplete"


# Older modules import these three. Kept so nothing breaks; new code should
# raise one of the HTTP-aware classes above instead.
class JobPostException(Exception):
    pass


class CandidateProfileException(Exception):
    pass


class ApplicationException(Exception):
    pass

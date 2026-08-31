from enum import Enum


class AdminAction(str, Enum):
    """What an administrator did. Stored on every AdminActionLog row."""

    USER_ACTIVATED = "user_activated"
    USER_DEACTIVATED = "user_deactivated"
    JOB_APPROVED = "job_approved"
    JOB_APPROVAL_REVOKED = "job_approval_revoked"


class AdminTarget(str, Enum):
    """What the action was done to. Not a foreign key: the log has to survive
    the row it describes, and a real FK with ON DELETE CASCADE would erase the
    record of a deletion at exactly the moment it matters."""

    USER = "user"
    JOB_POST = "job_post"

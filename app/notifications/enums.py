from enum import Enum


class NotificationChannel(str, Enum):
    EMAIL = "email"
    IN_APP = "in_app"


class NotificationStatus(str, Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

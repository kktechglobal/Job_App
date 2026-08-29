from enum import Enum


class SalaryType(str, Enum):
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class JobLevel(str, Enum):
    ENTRY = "entry"
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    LEAD = "lead"
    EXECUTIVE = "executive"


class ExperienceLevel(str, Enum):
    NONE = "none"
    ONE_TO_TWO_YEARS = "1-2_years"
    THREE_TO_FIVE_YEARS = "3-5_years"
    SIX_TO_TEN_YEARS = "6-10_years"
    TEN_PLUS_YEARS = "10_plus_years"


class JobType(str, Enum):
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    TEMPORARY = "temporary"


class SubscriptionPlan(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PREMIUM = "premium"


class Currency(str, Enum):
    NGN = "NGN"
    USD = "USD"
    GBP = "GBP"
    EUR = "EUR"

from enum import Enum


class OrganizationType(str, Enum):
    SOLE_PROPRIETORSHIP = "sole_proprietorship"
    PARTNERSHIP = "partnership"
    PRIVATE_LIMITED = "private_limited"
    PUBLIC_LIMITED = "public_limited"
    NGO = "ngo"
    GOVERNMENT = "government"


class IndustryType(str, Enum):
    TECHNOLOGY = "technology"
    FINANCE = "finance"
    HEALTHCARE = "healthcare"
    EDUCATION = "education"
    RETAIL = "retail"
    MANUFACTURING = "manufacturing"
    AGRICULTURE = "agriculture"
    CONSTRUCTION = "construction"
    OTHER = "other"


class TeamSize(str, Enum):
    """A band the employer picks, not a headcount."""

    SOLO = "1"
    SMALL = "2-10"
    MEDIUM = "11-50"
    LARGE = "51-200"
    ENTERPRISE = "201-500"
    HUGE = "500+"

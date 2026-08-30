from enum import Enum


class PromotionPlan(str, Enum):
    FEATURED = "featured"
    HIGHLIGHTED = "highlighted"
    BOTH = "both"

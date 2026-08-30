"""Enums shared by more than one module."""

from enum import Enum


class SocialPlatform(str, Enum):
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    GITHUB = "github"
    WEBSITE = "website"


class PaymentProvider(str, Enum):
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"
    STRIPE = "stripe"


class CardBrand(str, Enum):
    VISA = "visa"
    MASTERCARD = "mastercard"
    VERVE = "verve"
    AMEX = "amex"
    OTHER = "other"

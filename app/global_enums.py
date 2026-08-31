"""Enums used by more than one package.

An enum lives here only when two or more packages import it. Anything used by
a single package stays in that package's own enums.py -- app/jobs/enums.py,
app/users/enums.py and so on -- so that moving a domain does not drag along
values nobody else needs.

The comment above each class names its consumers. If a class ends up with only
one, move it back down into that package; if a package-local enum gains a
second consumer, move it up here.
"""

from enum import Enum


# Used by:
#   app/candidates  -- CandidateSocialLink.platform
#   app/companies   -- CompanySocialLink.platform
# One shared list so a candidate and a company cannot end up describing the
# same website with two different spellings.
class SocialPlatform(str, Enum):
    FACEBOOK = "facebook"
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    YOUTUBE = "youtube"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"
    GITHUB = "github"
    WEBSITE = "website"


# Used by:
#   app/candidates  -- CandidateCard.provider
#   app/companies   -- EmployerCard.provider
# The payment processor that holds the card, NOT the card network. Storing a
# brand here is the bug that shipped in the first version of the card schemas.
class PaymentProvider(str, Enum):
    PAYSTACK = "paystack"
    FLUTTERWAVE = "flutterwave"
    STRIPE = "stripe"


# Used by:
#   app/candidates  -- CandidateCard.brand
#   app/companies   -- EmployerCard.brand
# The card network, for display only -- it exists so a page can render
# "Visa ****4242" without going back to the provider.
class CardBrand(str, Enum):
    VISA = "visa"
    MASTERCARD = "mastercard"
    VERVE = "verve"
    AMEX = "amex"
    OTHER = "other"

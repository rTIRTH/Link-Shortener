"""Which features are free and which will need a paid plan.

Nothing is paid yet, so `can()` says yes to everybody. When subscriptions arrive:
  1. put the feature's name in PAID, and
  2. make has_paid_plan() look at the user's plan.
Every page and route already asks `can()` (templates call `can('tags')`), so nothing else changes.
"""

# Every feature that can be put behind a plan. Basics (links, QR codes, analytics, schedule,
# password) are deliberately not listed: they stay free.
FEATURES = ("click_limit", "tags", "archive", "csv_import", "preview", "utm", "qr_style",
            "color_schemes", "alerts")

PAID: frozenset[str] = frozenset()  # later e.g. frozenset({"click_limit", "tags"})


def has_paid_plan(user) -> bool:
    """Plans do not exist yet. This is the one place to change when they do."""
    return False


def can(user, feature: str) -> bool:
    if feature not in FEATURES:
        raise KeyError(feature)  # a typo in the code, never something a visitor can cause
    return feature not in PAID or has_paid_plan(user)


def require(user, feature: str) -> None:
    """Raise ValueError (shown to the person as a message) if their plan does not include it."""
    if not can(user, feature):
        raise ValueError("This feature is part of a paid plan.")

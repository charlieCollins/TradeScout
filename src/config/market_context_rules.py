"""
Market Context Rules Configuration

Defines system-wide rules for how to interpret market data in different session states.
These rules provide consistent behavior across the entire application.

Key Principles:
1. Always have a fallback when preferred data is NULL
2. Be explicit about what each field means in each context
3. Document assumptions about Polygon API behavior
"""

from typing import Dict, List, Any, Optional

# Field mapping rules for different market sessions
# Each entry is a list of fields in priority order (first non-NULL wins)
# VERIFIED 2025-09-29: closed_post session mappings work correctly
FIELD_MAPPINGS = {
    "current_price": {
        # Premarket: Use minute bar data (real-time), fallback to previous close
        "premarket": ["min_close", "prevday_close"],

        # Regular: Use min close (real-time ish)
        "regular": ["min_close"],

        # Afterhours: Use minute bar (real-time AH price), fallback to regular close
        "afterhours": ["min_close", "day_close"],

        # Closed (both pre and post): Use most recent available price
        "closed": ["day_close", "prevday_close"],
        "closed_pre": ["day_close", "prevday_close"],
        "closed_post": ["day_close", "prevday_close"],
    },

    "reference_price": {
        # What to compare against for change calculations
        "premarket": ["prevday_close"],           # Compare to yesterday's close
        "regular": ["prevday_close"],             # Compare to yesterday's close
        "afterhours": ["day_close", "prevday_close"],  # Compare to today's regular close
        "closed": ["prevday_close"],              # Compare to last known close
        "closed_pre": ["prevday_close"],
        "closed_post": ["prevday_close"],
    },

    "volume": {
        # Which volume field represents current activity
        "premarket": ["min_volume"],              # Premarket minute volume
        "regular": ["min_volume"],  # Regular session total
        "afterhours": ["min_volume"],             # AH minute volume
        "closed": ["prevday_volume"],             # Yesterday's volume
        "closed_pre": ["prevday_volume"],
        "closed_post": ["prevday_volume"],
    },

    "session_open": {
        # Opening price for the current session
        "premarket": ["prevday_close"],           # Premarket "opens" at prev close
        "regular": ["day_open"],                  # Regular session open
        "afterhours": ["day_close"],              # AH "opens" at regular close
        "closed": ["prevday_close"],              # No real open when closed
        "closed_pre": ["prevday_close"],
        "closed_post": ["prevday_close"],
    }
}


# Minimum data requirements for calculations
# Which fields MUST be non-NULL for valid calculations
REQUIRED_FIELDS = {
    "change_calculation": {
        # Fields required to calculate price change
        "all_sessions": ["prevday_close"],  # Always need previous close
    },
    "volume_analysis": {
        # Fields required for volume analysis
        "premarket": ["min_volume"],
        "regular": ["day_volume"],
        "afterhours": ["min_volume"],
        "closed": ["prevday_volume"],
    }
}

# Rules about data interpretation
# Empirically verified behaviors - Updated 2025-09-29 during closed_post session
DATA_RULES = {
    "prevday": {
        "description": "Previous trading session's data (NOT necessarily yesterday)",
        "notes": [
            "VERIFIED 2025-09-29: On Monday, prevday was Friday (last trading day) [VERIFIED]",
            "Represents the most recent COMPLETED regular trading session [VERIFIED]",
            "Always represents the previous trading day's regular session close [VERIFIED]"
        ]
    },
    "day": {
        "description": "Current calendar day's regular trading session (9:30 AM - 4:00 PM ET)",
        "notes": [
            "VERIFIED 2025-09-29: Contains today's regular session close (254.43 at 4 PM) [VERIFIED]",
            "Present on trading days, represents the completed regular session [VERIFIED]",
            "Represents ONLY regular hours, not extended hours [VERIFIED - different from min]"
        ]
    },
    "min": {
        "description": "Most recent minute bar from ANY session (including extended hours)",
        "notes": [
            "VERIFIED 2025-09-29: Updates during afterhours (AAPL 254.2 at 7:39 PM) [VERIFIED]",
            "Provides real-time price during extended hours [VERIFIED]",
            "Different from day.close (254.2 vs 254.43) showing AH movement [VERIFIED]",
            "May be NULL for low-volume stocks with no recent trades [PARTIALLY VERIFIED - was NULL before fix]",
            "Timestamp indicates when the minute bar occurred [VERIFIED - accurate timestamps]"
        ]
    }
}

# Fallback strategies when all fields are NULL
# Session-specific behaviors verified through testing
SESSION_BEHAVIORS_VERIFIED = {
    "closed_post": {
        "verified_date": "2025-09-29 21:00 ET",
        "observations": [
            "current_price correctly uses day_close (254.43) as primary source",
            "reference_price correctly uses prevday_close (255.46) for comparisons",
            "volume correctly uses prevday_volume for reference",
            "min data still updates during closed_post (254.2 at 7:39 PM)",
            "day data persists from regular session close (4 PM)",
            "prevday correctly references Friday on Monday (skipping weekend)"
        ]
    },
    "afterhours": {
        "verified_date": "2025-09-29 19:55 ET",
        "observations": [
            "min_close updates in real-time (AAPL 254.2, MSFT 514.75)",
            "min_close differs from day_close showing AH movement",
            "min timestamps accurate (23:39 UTC = 7:39 PM ET)",
            "Works even during initial confusion about holiday status"
        ]
    }
}

NULL_HANDLING_STRATEGY = {
    "current_price": {
        "action": "exclude_from_results",
        "reason": "Cannot determine current price for calculations"
    },
    "reference_price": {
        "action": "exclude_from_results",
        "reason": "Cannot calculate change without reference"
    },
    "volume": {
        "action": "treat_as_zero",
        "reason": "No trading volume is valid (0 volume)"
    }
}


def get_field_for_context(
    field_type: str,
    session: str,
    available_data: Dict[str, Any]
) -> Optional[Any]:
    """
    Get the appropriate field value based on context and availability.

    Args:
        field_type: Type of field needed (e.g., 'current_price', 'volume')
        session: Current market session
        available_data: Dictionary of available data fields

    Returns:
        The first non-NULL value from the priority list, or None if all are NULL
    """
    if field_type not in FIELD_MAPPINGS:
        return None

    session_mappings = FIELD_MAPPINGS[field_type].get(session, [])

    for field_name in session_mappings:
        value = available_data.get(field_name)
        if value is not None:
            return value

    return None




def validate_required_fields(
    operation: str,
    session: str,
    available_data: Dict[str, Any]
) -> bool:
    """
    Check if required fields are available for an operation.

    Args:
        operation: The operation being performed (e.g., 'change_calculation')
        session: Current market session
        available_data: Dictionary of available data fields

    Returns:
        True if all required fields are non-NULL, False otherwise
    """
    if operation not in REQUIRED_FIELDS:
        return True  # No requirements defined, assume OK

    requirements = REQUIRED_FIELDS[operation]

    # Check session-specific requirements
    session_fields = requirements.get(session, [])
    for field in session_fields:
        if available_data.get(field) is None:
            return False

    # Check all-session requirements
    all_session_fields = requirements.get("all_sessions", [])
    for field in all_session_fields:
        if available_data.get(field) is None:
            return False

    return True
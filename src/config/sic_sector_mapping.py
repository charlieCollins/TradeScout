"""SIC code to sector mapping for TradeScout fundamentals classification.

This module provides a simple mapping from SIC (Standard Industrial Classification)
major groups (first 2 digits) to broad investment sectors. This is a pragmatic
approach to enable sector-based filtering until more sophisticated classification
can be implemented.

See docs/SECTOR_CLASSIFICATION.md for detailed explanation of our approach.
"""

# SIC Major Group (first 2 digits) to Sector mapping
SIC_SECTOR_MAPPING = {
    # Technology & Software
    "35": "Technology",        # Industrial machinery & computer equipment
    "36": "Technology",        # Electronic equipment
    "38": "Technology",        # Instruments & related products
    "73": "Technology",        # Business services (software, consulting)

    # Financials
    "60": "Financials",        # Banking
    "61": "Financials",        # Credit agencies
    "62": "Financials",        # Security brokers
    "63": "Financials",        # Insurance carriers
    "64": "Financials",        # Insurance agents
    "67": "Financials",        # Holding companies

    # Real Estate (separate from Financials for REIT classification)
    "65": "Real Estate",       # Real estate
    "66": "Real Estate",       # Combined real estate, insurance, etc.

    # Healthcare & Pharmaceuticals
    "28": "Healthcare",        # Chemicals (includes pharmaceuticals)
    "80": "Healthcare",        # Health services
    "87": "Healthcare",        # Engineering & management services (includes research)

    # Communication Services
    "48": "Communication Services",  # Communications
    "78": "Communication Services",  # Motion pictures
    "27": "Communication Services",  # Printing & publishing

    # Consumer Discretionary
    "23": "Consumer Discretionary",  # Apparel
    "25": "Consumer Discretionary",  # Furniture
    "39": "Consumer Discretionary",  # Miscellaneous manufacturing
    "50": "Consumer Discretionary",  # Wholesale trade - durable goods
    "55": "Consumer Discretionary",  # Automotive dealers
    "56": "Consumer Discretionary",  # Apparel stores
    "57": "Consumer Discretionary",  # Home furniture stores
    "58": "Consumer Discretionary",  # Eating & drinking places
    "59": "Consumer Discretionary",  # Miscellaneous retail
    "70": "Consumer Discretionary",  # Hotels & lodging
    "75": "Consumer Discretionary",  # Auto repair & services
    "76": "Consumer Discretionary",  # Miscellaneous repair services
    "79": "Consumer Discretionary",  # Amusement & recreation

    # Consumer Staples
    "20": "Consumer Staples",   # Food products
    "21": "Consumer Staples",   # Tobacco products
    "54": "Consumer Staples",   # Food stores

    # Energy
    "13": "Energy",            # Oil & gas extraction
    "29": "Energy",            # Petroleum refining
    "46": "Energy",            # Pipelines (except natural gas)

    # Materials
    "10": "Materials",         # Metal mining
    "12": "Materials",         # Coal mining
    "14": "Materials",         # Mining & quarrying of nonmetallic minerals
    "24": "Materials",         # Lumber & wood products
    "26": "Materials",         # Paper products
    "30": "Materials",         # Rubber & plastics
    "32": "Materials",         # Stone, clay, glass products
    "33": "Materials",         # Primary metal industries
    "34": "Materials",         # Fabricated metal products

    # Industrials
    "15": "Industrials",       # Building construction
    "16": "Industrials",       # Heavy construction
    "17": "Industrials",       # Construction - special trade contractors
    "37": "Industrials",       # Transportation equipment
    "40": "Industrials",       # Railroad transportation
    "41": "Industrials",       # Local passenger transportation
    "42": "Industrials",       # Motor freight transportation
    "43": "Industrials",       # U.S. Postal Service
    "44": "Industrials",       # Water transportation
    "45": "Industrials",       # Transportation by air
    "47": "Industrials",       # Transportation services
    "82": "Industrials",       # Educational services

    # Utilities
    "49": "Utilities",         # Electric, gas, sanitary services
}


def get_sector_from_sic(sic_code: str) -> str:
    """Map SIC code to broad sector using first 2 digits.

    Args:
        sic_code: 4-digit SIC code (e.g., "3571")

    Returns:
        Broad sector name or "Other" if unmapped

    Example:
        >>> get_sector_from_sic("3571")  # Electronic Computers
        "Technology"
        >>> get_sector_from_sic("6022")  # State Commercial Banks
        "Financials"
    """
    if not sic_code or len(sic_code) < 2:
        return "Other"

    major_group = sic_code[:2]
    return SIC_SECTOR_MAPPING.get(major_group, "Other")


def get_all_sectors() -> list[str]:
    """Get list of all defined sectors."""
    return sorted(set(SIC_SECTOR_MAPPING.values()) | {"Other"})


def get_sic_codes_for_sector(sector: str) -> list[str]:
    """Get list of SIC major groups (2-digit) for a given sector.

    Args:
        sector: Sector name (e.g., "Technology")

    Returns:
        List of 2-digit SIC codes for that sector
    """
    return [sic for sic, sec in SIC_SECTOR_MAPPING.items() if sec == sector]
"""Keyword-based merchant classification for HSA likelihood.

Used in two places:
  1. apply_auto_flag() — flags transactions from likely-HSA merchants as
     'potential_hsa' even when Teller's category didn't catch them.
  2. GET /bank/transactions/merchants — annotates each merchant group with
     hsa_likelihood so the UI can sort and label them appropriately.

All matching is case-insensitive substring against the normalized merchant name.
"""

from __future__ import annotations

import re
from typing import Literal

# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------

def normalize_merchant_name(name: str) -> str:
    """Strip store numbers and noise from a raw counterparty name.

    Examples:
        "MCDONALD'S #4829"          → "MCDONALD'S"
        "STARBUCKS 0291"             → "STARBUCKS"
        "DR SMITH OPTOMETRY INC"     → "DR SMITH OPTOMETRY"
        "CVS PHARMACY"               → "CVS PHARMACY"
    """
    if not name:
        return name
    # Strip store/location codes: #4829, #ABC12
    name = re.sub(r"\s*#\w+", "", name)
    # Strip trailing bare numbers (store codes): STARBUCKS 0291
    name = re.sub(r"\s+\d+$", "", name)
    # Strip common business suffixes
    name = re.sub(
        r"\s+(INC|LLC|CORP|CO|LTD|DBA)\.?\s*$", "", name, flags=re.IGNORECASE
    )
    return re.sub(r"\s+", " ", name).strip()


# ---------------------------------------------------------------------------
# Keyword lists
# ---------------------------------------------------------------------------

# Matched against normalized, lowercased merchant name.
# Positive signals — merchant is likely an HSA-eligible provider.
HSA_LIKELY_KEYWORDS: list[str] = [
    # General medical
    "hospital",
    "clinic",
    "medical",
    "urgent care",
    "emergency",
    "surgery",
    "surgical",
    "physician",
    "doctor",
    " dr ",
    "md ",
    # Dental
    "dental",
    "dentist",
    "orthodont",
    "endodont",
    "periodont",
    # Vision
    "vision",
    "optical",
    "optometry",
    "optometrist",
    "eyecare",
    "eye care",
    "lenscrafters",
    "pearle vision",
    "america's best",
    "for eyes",
    "eyeglass world",
    # Pharmacy / drug stores (chain names help when category is wrong)
    "pharmacy",
    "walgreens",
    "cvs",
    "rite aid",
    "duane reade",
    # Mental health
    "therapy",
    "therapist",
    "counseling",
    "counselor",
    "psychiatr",
    "psycholog",
    "behavioral health",
    "mental health",
    # Physical therapy / rehab
    "physical therapy",
    "occupational therapy",
    "speech therapy",
    "rehab",
    "chiropractic",
    "chiropractor",
    # Lab / imaging
    "laboratory",
    " lab ",
    "radiology",
    "imaging",
    "diagnostic",
    # Hearing
    "audiology",
    "audiologist",
    "hearing aid",
    "miracle ear",
    # Other
    "health system",
    "health center",
    "health services",
    "healthcare",
    "medcare",
    "medifast",
]

# Negative signals — merchant is very unlikely to have HSA-eligible expenses.
HSA_UNLIKELY_KEYWORDS: list[str] = [
    # Fast food
    "mcdonald",
    "burger king",
    "wendy's",
    "chipotle",
    "taco bell",
    "taco john",
    "subway",
    "chick-fil",
    "popeyes",
    "domino",
    "pizza hut",
    "little caesar",
    "papa john",
    "panda express",
    "five guys",
    "sonic drive",
    "arby's",
    "hardee",
    "carl's jr",
    "jack in the box",
    "dairy queen",
    "culver",
    "whataburger",
    "shake shack",
    "in-n-out",
    "raising cane",
    "wingstop",
    "jersey mike",
    "jimmy john",
    "firehouse sub",
    "portillo",
    # Coffee / bakery
    "starbucks",
    "dunkin",
    "tim horton",
    "panera",
    "einstein bagel",
    "caribou coffee",
    "dutch bros",
    # Gas / fuel
    "shell oil",
    "exxon",
    "bp station",
    "chevron",
    "sunoco",
    "speedway",
    "marathon gas",
    "citgo",
    "phillips 66",
    "quiktrip",
    "casey's general",
    "circle k",
    "holiday station",
    # Convenience (without pharmacy)
    "wawa",
    "sheetz",
    "7-eleven",
    "7eleven",
    "kwik trip",
    # Grocery / big box
    "walmart",
    "target",
    "kroger",
    "safeway",
    "publix",
    "whole foods",
    "trader joe",
    "aldi",
    "costco",
    "sam's club",
    "meijer",
    "wegmans",
    "stop & shop",
    "giant food",
    "food lion",
    "h-e-b",
    "sprouts farmer",
    # Entertainment / streaming
    "netflix",
    "spotify",
    "hulu",
    "disney+",
    "apple tv",
    "amazon prime",
    "hbo max",
    "paramount+",
    "peacock",
    "amc theaters",
    "regal cinema",
    "cinemark",
    "fandango",
    # Alcohol
    "brewery",
    "brewing",
    "liquor",
    "winery",
    "wine & spirit",
    "total wine",
    "binny",
    "abc fine wine",
    # Department / apparel
    "nordstrom",
    "macy",
    "tj maxx",
    "marshalls",
    "ross dress",
    "old navy",
    "gap store",
    "h&m",
    "forever 21",
    "victoria secret",
    "bath & body",
    "hot topic",
    # Home improvement
    "home depot",
    "lowe's",
    "menards",
    "ace hardware",
    "true value",
    # Auto
    "jiffy lube",
    "valvoline",
    "midas",
    "pep boys",
    "autozone",
    "o'reilly auto",
    "advance auto",
    "napa auto",
    # Pet
    "petco",
    "petsmart",
    "pet supplies",
]


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------

HsaLikelihood = Literal["likely", "unlikely", "unknown"]


def classify_merchant(normalized_name: str) -> HsaLikelihood:
    """Return HSA likelihood for a normalized merchant name.

    Checks likely keywords first; if matched returns 'likely'.
    Then checks unlikely keywords; if matched returns 'unlikely'.
    Otherwise returns 'unknown'.
    """
    lower = normalized_name.lower()
    for kw in HSA_LIKELY_KEYWORDS:
        if kw in lower:
            return "likely"
    for kw in HSA_UNLIKELY_KEYWORDS:
        if kw in lower:
            return "unlikely"
    return "unknown"

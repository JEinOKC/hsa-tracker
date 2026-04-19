"""Parser for CVS Financial Summary CSV exports.

CVS pharmacy users can export their prescription spending history from cvs.com
under Prescriptions → Financial Summary → Download. The export has a non-standard
structure:

    Title,Date,Total Rx Spend
    Financial Summary,"May 19, 2025 - Apr 19, 2026",$386.96
    (blank line)
    Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid,...
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-03-27,CVS Pharmacy®,$10.00,...
    ...
    (blank lines)
    This report may not reflect all medicines dispensed during the specified period.
    ...

This module contains only pure parsing logic. No database access.
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional


class CvsParseError(Exception):
    """Raised when the uploaded file cannot be parsed as a CVS Financial Summary."""


# The column header that marks the start of the data rows
_DATA_HEADER_FIELD = "Member Name"

# Columns we care about (case-insensitive match)
_COL_MEMBER = "member name"
_COL_DRUG = "drug name"
_COL_RX = "rx #"
_COL_DATE = "last filled"
_COL_PHARMACY = "pharmacy name"
_COL_YOU_PAID = "you paid"


@dataclass
class ParsedFill:
    member_name: Optional[str]    # cleaned (age suffix stripped)
    drug_name: str
    rx_number: Optional[str]
    fill_date: date
    amount_paid: Decimal
    pharmacy: Optional[str]


def _strip_dollar(value: str) -> Optional[Decimal]:
    """Convert '$10.00' or '-' or '' to Decimal or None."""
    v = value.strip()
    if not v or v == "-":
        return None
    v = v.lstrip("$").replace(",", "").strip()
    try:
        return Decimal(v)
    except InvalidOperation:
        return None


def _clean_member_name(raw: str) -> Optional[str]:
    """Strip ' age NN' suffix from CVS member name field."""
    if not raw or raw.strip() == "-":
        return None
    cleaned = re.sub(r"\s+age\s+\d+$", "", raw.strip(), flags=re.IGNORECASE)
    return cleaned.strip() or None


def _is_disclaimer_row(row: list[str]) -> bool:
    """Return True if the row looks like a trailing disclaimer/note line."""
    joined = " ".join(row).strip()
    return bool(joined) and joined[0].isalpha() and len(joined) > 20


def parse_cvs_financial_summary(file_content: bytes) -> list[ParsedFill]:
    """Parse a CVS Financial Summary CSV and return a list of prescription fills.

    Args:
        file_content: Raw bytes of the uploaded CSV file.

    Returns:
        List of ParsedFill objects, one per data row.

    Raises:
        CvsParseError: If the file cannot be recognised as a CVS Financial Summary.
    """
    try:
        text = file_content.decode("utf-8-sig")  # strip BOM if present
    except UnicodeDecodeError:
        try:
            text = file_content.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise CvsParseError("File encoding not supported. Please upload a UTF-8 or Latin-1 CSV.") from exc

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    # Locate the header row (the one that starts with "Member Name")
    header_idx = None
    for i, row in enumerate(rows):
        if row and row[0].strip().lower() == _DATA_HEADER_FIELD.lower():
            header_idx = i
            break

    if header_idx is None:
        raise CvsParseError(
            "Could not find the data header row ('Member Name'). "
            "Please upload an unmodified CVS Financial Summary CSV."
        )

    header = [h.strip().lower() for h in rows[header_idx]]

    def _col(name: str) -> Optional[int]:
        try:
            return header.index(name)
        except ValueError:
            return None

    col_member = _col(_COL_MEMBER)
    col_drug = _col(_COL_DRUG)
    col_rx = _col(_COL_RX)
    col_date = _col(_COL_DATE)
    col_pharmacy = _col(_COL_PHARMACY)
    col_you_paid = _col(_COL_YOU_PAID)

    if col_drug is None or col_date is None or col_you_paid is None:
        raise CvsParseError(
            "Required columns ('Drug Name', 'Last Filled', 'You paid') not found. "
            "Please upload an unmodified CVS Financial Summary CSV."
        )

    fills: list[ParsedFill] = []

    for row in rows[header_idx + 1:]:
        # Skip blank rows
        if not any(cell.strip() for cell in row):
            continue

        # Stop at disclaimer/footer text (first cell is a long sentence, not a name)
        if len(row) < 3 or _is_disclaimer_row(row[:1]):
            break

        def _get(idx: Optional[int]) -> str:
            if idx is None or idx >= len(row):
                return ""
            return row[idx].strip()

        drug_name = _get(col_drug)
        if not drug_name or drug_name == "-":
            continue  # skip rows with no drug name

        fill_date_str = _get(col_date)
        try:
            fill_date = date.fromisoformat(fill_date_str)
        except (ValueError, TypeError):
            continue  # skip rows with unparseable dates

        amount_paid = _strip_dollar(_get(col_you_paid))
        if amount_paid is None:
            continue  # skip rows with no payment amount

        fills.append(ParsedFill(
            member_name=_clean_member_name(_get(col_member)) if col_member is not None else None,
            drug_name=drug_name,
            rx_number=_get(col_rx) or None if col_rx is not None else None,
            fill_date=fill_date,
            amount_paid=amount_paid,
            pharmacy=_get(col_pharmacy) or None if col_pharmacy is not None else None,
        ))

    if not fills:
        raise CvsParseError(
            "No prescription fill rows found in the file. "
            "The file may be empty or not a CVS Financial Summary export."
        )

    return fills

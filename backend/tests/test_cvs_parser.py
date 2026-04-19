"""Unit tests for the CVS Financial Summary CSV parser.

No database required — pure function tests.
"""

import textwrap
from datetime import date
from decimal import Decimal

import pytest

from app.services.cvs_parser import (
    CvsParseError,
    ParsedFill,
    parse_cvs_financial_summary,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# Mirrors the real CVS Financial Summary format
REAL_CVS_CSV = textwrap.dedent("""\
    Title,Date,Total Rx Spend
    Financial Summary,"May 19, 2025 - Apr 19, 2026",$386.96

    Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid,Your Plan(s) Paid,Primary Plan Paid,Secondary Plan Paid,Manufacturer Discount,Other Adjustments,Discount Applied,Amount Applied To Deductible,Coupon Applied,Prescription Payment Status
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-03-27,CVS Pharmacy®,$10.00,$0.00,$0.00,$0.00,-,-,-,$0.00,$0.00,-
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-02-27,CVS Pharmacy®,$10.00,$0.00,$0.00,$0.00,-,-,-,$0.00,-,-
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-01-24,CVS Pharmacy®,$10.00,$0.00,$0.00,$0.00,-,-,-,$0.00,-,-
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2025-12-28,CVS Pharmacy®,$51.08,$0.00,$0.00,$0.00,-,-,-,$0.00,-,-
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2025-11-11,CVS Pharmacy®,$51.08,$0.00,$0.00,$0.00,-,-,-,$0.00,-,-
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2025-10-12,CVS Pharmacy®,$51.08,$0.00,$0.00,$0.00,-,-,-,$0.00,-,-
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2025-09-12,CVS Pharmacy®,$51.08,$0.00,$0.00,$0.00,-,-,-,$0.00,-,-
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2025-08-14,CVS Pharmacy®,$51.08,$0.00,$0.00,$0.00,-,-,-,$0.00,-,-
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2025-07-12,CVS Pharmacy®,$50.78,$0.00,$0.00,$0.00,-,-,-,$0.00,-,-
    JAMES age 39,WIXELA 250-50 INHUB,1351781,2025-06-15,CVS Pharmacy®,$50.78,$0.00,$0.00,$0.00,-,-,-,$0.00,-,-


    This report may not reflect all medicines dispensed during the specified period.
    Costs displayed may not reflect coverage from any supplemental insurance plans.
    "Other adjustments may include supplemental insurance coverage, manufacturer coupons or other discounts."
    One or more of your prescriptions has a rebate applied and will be counted toward your plan accumulation.
""").encode("utf-8")


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_parse_real_cvs_export_row_count():
    fills = parse_cvs_financial_summary(REAL_CVS_CSV)
    assert len(fills) == 10


def test_parse_first_row_fields():
    fills = parse_cvs_financial_summary(REAL_CVS_CSV)
    first = fills[0]
    assert first.drug_name == "WIXELA 250-50 INHUB"
    assert first.rx_number == "1351781"
    assert first.fill_date == date(2026, 3, 27)
    assert first.amount_paid == Decimal("10.00")
    assert first.pharmacy == "CVS Pharmacy®"


def test_parse_last_row_amount():
    fills = parse_cvs_financial_summary(REAL_CVS_CSV)
    assert fills[-1].amount_paid == Decimal("50.78")
    assert fills[-1].fill_date == date(2025, 6, 15)


def test_member_name_strips_age_suffix():
    fills = parse_cvs_financial_summary(REAL_CVS_CSV)
    assert fills[0].member_name == "JAMES"


def test_member_name_strips_age_case_insensitive():
    csv_bytes = textwrap.dedent("""\
        Title,Date,Total Rx Spend
        Financial Summary,"Jan 1, 2026 - Apr 19, 2026",$10.00

        Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid
        Sarah Age 45,LISINOPRIL 10MG,9999999,2026-01-15,CVS Pharmacy®,$5.00
    """).encode("utf-8")
    fills = parse_cvs_financial_summary(csv_bytes)
    assert fills[0].member_name == "Sarah"


def test_dollar_sign_stripped_from_amounts():
    fills = parse_cvs_financial_summary(REAL_CVS_CSV)
    for fill in fills:
        assert isinstance(fill.amount_paid, Decimal)


def test_varying_amounts_parsed_correctly():
    fills = parse_cvs_financial_summary(REAL_CVS_CSV)
    amounts = [f.amount_paid for f in fills]
    assert Decimal("10.00") in amounts
    assert Decimal("51.08") in amounts
    assert Decimal("50.78") in amounts


def test_disclaimer_rows_excluded():
    fills = parse_cvs_financial_summary(REAL_CVS_CSV)
    drug_names = [f.drug_name for f in fills]
    for name in drug_names:
        assert "report may not" not in name.lower()
        assert "costs displayed" not in name.lower()


def test_blank_rows_skipped():
    """Extra blank lines between data and footer should not produce fills."""
    fills = parse_cvs_financial_summary(REAL_CVS_CSV)
    assert len(fills) == 10  # no phantom rows from blank lines


def test_bom_stripped():
    """UTF-8 BOM (\xef\xbb\xbf) at file start should not break parsing."""
    bom_csv = b"\xef\xbb\xbf" + REAL_CVS_CSV
    fills = parse_cvs_financial_summary(bom_csv)
    assert len(fills) == 10


# ---------------------------------------------------------------------------
# Multiple members
# ---------------------------------------------------------------------------


def test_multiple_members_parsed():
    csv_bytes = textwrap.dedent("""\
        Title,Date,Total Rx Spend
        Financial Summary,"Jan 1, 2026 - Apr 19, 2026",$30.00

        Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid
        JAMES age 39,WIXELA 250-50 INHUB,1351781,2026-01-10,CVS Pharmacy®,$10.00
        EMMA age 37,METFORMIN 500MG,2222222,2026-01-15,CVS Pharmacy®,$20.00
    """).encode("utf-8")
    fills = parse_cvs_financial_summary(csv_bytes)
    assert len(fills) == 2
    assert fills[0].member_name == "JAMES"
    assert fills[1].member_name == "EMMA"


# ---------------------------------------------------------------------------
# Error cases
# ---------------------------------------------------------------------------


def test_missing_member_name_header_raises():
    csv_bytes = textwrap.dedent("""\
        Title,Date,Total Rx Spend
        Financial Summary,"Jan 1, 2026",$0.00

        Name,Drug,Date,Amount
        James,Aspirin,2026-01-01,$5.00
    """).encode("utf-8")
    with pytest.raises(CvsParseError, match="Member Name"):
        parse_cvs_financial_summary(csv_bytes)


def test_missing_required_columns_raises():
    csv_bytes = textwrap.dedent("""\
        Title,Date,Total Rx Spend
        Financial Summary,"Jan 1, 2026",$0.00

        Member Name,Drug Name,RX #,Last Filled,Pharmacy Name
        JAMES age 39,WIXELA,1351781,2026-01-10,CVS Pharmacy®
    """).encode("utf-8")
    # Missing "You paid" column
    with pytest.raises(CvsParseError, match="You paid"):
        parse_cvs_financial_summary(csv_bytes)


def test_empty_data_section_raises():
    csv_bytes = textwrap.dedent("""\
        Title,Date,Total Rx Spend
        Financial Summary,"Jan 1, 2026",$0.00

        Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid

        This report may not reflect all medicines dispensed.
    """).encode("utf-8")
    with pytest.raises(CvsParseError, match="No prescription fill rows"):
        parse_cvs_financial_summary(csv_bytes)


def test_completely_wrong_file_raises():
    csv_bytes = b"name,email\njohn,john@example.com\n"
    with pytest.raises(CvsParseError):
        parse_cvs_financial_summary(csv_bytes)


def test_rows_with_dash_amount_skipped():
    """Rows where 'You paid' is '-' (e.g. fully covered) should be skipped."""
    csv_bytes = textwrap.dedent("""\
        Title,Date,Total Rx Spend
        Financial Summary,"Jan 1, 2026",$10.00

        Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid
        JAMES age 39,DRUG A,1111111,2026-01-10,CVS Pharmacy®,$10.00
        JAMES age 39,DRUG B,2222222,2026-01-15,CVS Pharmacy®,-
    """).encode("utf-8")
    fills = parse_cvs_financial_summary(csv_bytes)
    assert len(fills) == 1
    assert fills[0].drug_name == "DRUG A"


def test_rows_with_bad_date_skipped():
    csv_bytes = textwrap.dedent("""\
        Title,Date,Total Rx Spend
        Financial Summary,"Jan 1, 2026",$10.00

        Member Name,Drug Name,RX #,Last Filled,Pharmacy Name,You paid
        JAMES age 39,DRUG A,1111111,2026-01-10,CVS Pharmacy®,$10.00
        JAMES age 39,DRUG B,2222222,not-a-date,CVS Pharmacy®,$5.00
    """).encode("utf-8")
    fills = parse_cvs_financial_summary(csv_bytes)
    assert len(fills) == 1

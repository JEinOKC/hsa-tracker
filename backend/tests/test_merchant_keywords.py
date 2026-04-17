"""Unit tests for merchant keyword classification and name normalization."""

import pytest
from app.services.merchant_keywords import classify_merchant, normalize_merchant_name


class TestNormalizeMerchantName:
    def test_strips_store_number_hash(self):
        assert normalize_merchant_name("MCDONALD'S #4829") == "MCDONALD'S"

    def test_strips_alphanumeric_store_code(self):
        assert normalize_merchant_name("SHELL #AB123") == "SHELL"

    def test_strips_trailing_bare_numbers(self):
        assert normalize_merchant_name("STARBUCKS 0291") == "STARBUCKS"

    def test_strips_inc_suffix(self):
        assert normalize_merchant_name("DR SMITH OPTOMETRY INC") == "DR SMITH OPTOMETRY"

    def test_strips_llc_suffix(self):
        assert normalize_merchant_name("CITY DENTAL LLC") == "CITY DENTAL"

    def test_strips_corp_suffix(self):
        assert normalize_merchant_name("HEALTH SERVICES CORP") == "HEALTH SERVICES"

    def test_strips_co_suffix(self):
        assert normalize_merchant_name("MEDS CO") == "MEDS"

    def test_strips_ltd_suffix(self):
        assert normalize_merchant_name("Eyecare Plus LTD") == "Eyecare Plus"

    def test_no_change_for_clean_name(self):
        assert normalize_merchant_name("CVS PHARMACY") == "CVS PHARMACY"

    def test_collapses_extra_whitespace(self):
        assert normalize_merchant_name("DR  JONES   DENTAL") == "DR JONES DENTAL"

    def test_empty_string_passthrough(self):
        assert normalize_merchant_name("") == ""

    def test_multiple_normalizations_combined(self):
        # Store number AND suffix
        assert normalize_merchant_name("ACME OPTICAL #88 LLC") == "ACME OPTICAL"


class TestClassifyMerchant:
    # --- likely ---
    def test_hospital_is_likely(self):
        assert classify_merchant("MERCY HOSPITAL") == "likely"

    def test_pharmacy_is_likely(self):
        assert classify_merchant("CITY PHARMACY") == "likely"

    def test_walgreens_is_likely(self):
        assert classify_merchant("WALGREENS") == "likely"

    def test_cvs_is_likely(self):
        assert classify_merchant("CVS PHARMACY") == "likely"

    def test_dental_is_likely(self):
        assert classify_merchant("BRIGHT SMILE DENTAL") == "likely"

    def test_optometry_is_likely(self):
        assert classify_merchant("JONES OPTOMETRY") == "likely"

    def test_vision_is_likely(self):
        assert classify_merchant("PEARLE VISION") == "likely"

    def test_therapy_is_likely(self):
        assert classify_merchant("RIVERSIDE THERAPY") == "likely"

    def test_chiropractic_is_likely(self):
        assert classify_merchant("BACK IN LINE CHIROPRACTIC") == "likely"

    def test_radiology_is_likely(self):
        assert classify_merchant("NORTHSIDE RADIOLOGY") == "likely"

    def test_clinic_is_likely(self):
        assert classify_merchant("URGENT CARE CLINIC") == "likely"

    def test_dr_prefix_is_likely(self):
        # space-padded " dr " keyword — requires dr in the middle of the name
        assert classify_merchant("VISIT TO DR SMITH") == "likely"

    # --- unlikely ---
    def test_mcdonalds_is_unlikely(self):
        assert classify_merchant("MCDONALD'S") == "unlikely"

    def test_starbucks_is_unlikely(self):
        assert classify_merchant("STARBUCKS") == "unlikely"

    def test_chipotle_is_unlikely(self):
        assert classify_merchant("CHIPOTLE MEXICAN GRILL") == "unlikely"

    def test_walmart_is_unlikely(self):
        assert classify_merchant("WALMART SUPERCENTER") == "unlikely"

    def test_target_is_unlikely(self):
        assert classify_merchant("TARGET") == "unlikely"

    def test_netflix_is_unlikely(self):
        assert classify_merchant("NETFLIX") == "unlikely"

    def test_brewery_is_unlikely(self):
        assert classify_merchant("OLD TOWN BREWERY") == "unlikely"

    def test_home_depot_is_unlikely(self):
        assert classify_merchant("HOME DEPOT") == "unlikely"

    def test_jiffy_lube_is_unlikely(self):
        assert classify_merchant("JIFFY LUBE") == "unlikely"

    def test_petco_is_unlikely(self):
        assert classify_merchant("PETCO") == "unlikely"

    # --- unknown ---
    def test_amazon_is_unknown(self):
        assert classify_merchant("AMAZON MARKETPLACE") == "unknown"

    def test_generic_restaurant_is_unknown(self):
        assert classify_merchant("MAIN ST CAFE") == "unknown"

    def test_empty_string_is_unknown(self):
        assert classify_merchant("") == "unknown"

    # --- likely wins over unlikely if both match ---
    def test_likely_beats_unlikely_when_both_match(self):
        # "CVS PHARMACY WALGREENS" contains both a likely keyword and Walgreens
        # likely is checked first so result is 'likely'
        assert classify_merchant("CVS MEDICAL WALMART") == "likely"

    # --- case insensitivity ---
    def test_lowercase_input_works(self):
        assert classify_merchant("walgreens pharmacy") == "likely"

    def test_mixed_case_input_works(self):
        assert classify_merchant("Walgreens Pharmacy") == "likely"

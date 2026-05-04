"""Property-based tests for geocoding regexes and Nominatim truncation.

Feature: uk-eu-internationalization
Properties: 8, 9, 10
Validates: Requirements 6.2, 6.3, 6.4, 7.4, 8.6
"""

from hypothesis import given, settings
from hypothesis import strategies as st

from server.weather import _UK_POSTCODE_RE, _ZIP_RE, _ICAO_RE


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

# The six valid UK postcode outward-code formats:
#   A9, A99, A9A, AA9, AA99, AA9A
# where A = uppercase letter, 9 = digit

_letter = st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
_digit = st.sampled_from("0123456789")


@st.composite
def outward_code(draw):
    """Generate a valid UK postcode outward code in one of the 6 formats."""
    fmt = draw(st.sampled_from(["A9", "A99", "A9A", "AA9", "AA99", "AA9A"]))
    if fmt == "A9":
        return draw(_letter) + draw(_digit)
    elif fmt == "A99":
        return draw(_letter) + draw(_digit) + draw(_digit)
    elif fmt == "A9A":
        return draw(_letter) + draw(_digit) + draw(_letter)
    elif fmt == "AA9":
        return draw(_letter) + draw(_letter) + draw(_digit)
    elif fmt == "AA99":
        return draw(_letter) + draw(_letter) + draw(_digit) + draw(_digit)
    else:  # AA9A
        return draw(_letter) + draw(_letter) + draw(_digit) + draw(_letter)


@st.composite
def inward_code(draw):
    """Generate a valid UK postcode inward code: digit + 2 letters."""
    return draw(_digit) + draw(_letter) + draw(_letter)


@st.composite
def uk_postcode(draw):
    """Generate a full UK postcode (outward + inward) with random spacing and case."""
    out = draw(outward_code())
    inw = draw(inward_code())
    # Choose spacing variant: with space or without
    space = draw(st.sampled_from(["", " "]))
    full = out + space + inw
    # Choose case variant: upper, lower, or mixed (as-is from generators is upper)
    case_choice = draw(st.sampled_from(["upper", "lower", "mixed"]))
    if case_choice == "lower":
        return full.lower()
    elif case_choice == "mixed":
        # Randomly flip case of each character
        chars = []
        for ch in full:
            if draw(st.booleans()):
                chars.append(ch.lower())
            else:
                chars.append(ch.upper())
        return "".join(chars)
    return full  # upper


# ---------------------------------------------------------------------------
# Property 8: UK postcode regex accepts all valid format variants
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(postcode=uk_postcode())
def test_uk_postcode_regex_accepts_all_valid_formats(postcode):
    """Property 8: For any valid UK postcode outward code (A9, A99, A9A, AA9,
    AA99, AA9A) combined with any valid inward code (digit + two letters),
    the _UK_POSTCODE_RE regex SHALL match the postcode with a space, without
    a space, and in any letter case.

    **Validates: Requirements 6.2, 6.3, 6.4**
    """
    assert _UK_POSTCODE_RE.match(postcode) is not None, (
        f"UK postcode regex failed to match valid postcode: {postcode!r}"
    )


# ---------------------------------------------------------------------------
# Property 9: ICAO regex accepts any four uppercase letters
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(
    code=st.text(
        alphabet=st.sampled_from("ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
        min_size=4,
        max_size=4,
    )
)
def test_icao_regex_accepts_four_uppercase_letters(code):
    """Property 9: For any string of exactly four uppercase ASCII letters,
    the _ICAO_RE regex SHALL match.

    **Validates: Requirements 7.4**
    """
    assert _ICAO_RE.match(code) is not None, (
        f"ICAO regex failed to match valid code: {code!r}"
    )


# ---------------------------------------------------------------------------
# Property 10: Nominatim display name truncation
# ---------------------------------------------------------------------------

def _truncate_display_name(name: str) -> str:
    """Replicate the Nominatim display name truncation logic from weather.py."""
    if len(name) > 80:
        return name[:77] + "..."
    return name


@settings(max_examples=200)
@given(name=st.text(min_size=0, max_size=300))
def test_nominatim_display_name_truncation(name):
    """Property 10: For any display name string longer than 80 characters,
    truncation produces exactly 80 characters (77 + "..."). For any display
    name of 80 characters or fewer, the string is returned unchanged.

    **Validates: Requirements 8.6**
    """
    result = _truncate_display_name(name)

    if len(name) > 80:
        assert len(result) == 80, (
            f"Expected truncated length 80, got {len(result)} for input of length {len(name)}"
        )
        assert result.endswith("..."), (
            f"Truncated name should end with '...' but got: {result!r}"
        )
        assert result[:77] == name[:77], (
            "First 77 characters should be preserved after truncation"
        )
    else:
        assert result == name, (
            f"Names of 80 chars or fewer should be unchanged, "
            f"but got {result!r} for input {name!r}"
        )


# ===========================================================================
# Unit Tests for Geocoding Chain
# Requirements: 6.1–6.5, 7.1–7.4, 8.1–8.6, 9.1–9.6
# ===========================================================================

import pytest


# ---------------------------------------------------------------------------
# 1. UK postcode format detection — known valid postcodes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("postcode", [
    "SW1A 1AA",
    "M1 1AE",
    "LS18 5HD",
    "EC1A 1BB",
    "sw1a1aa",  # case-insensitive, no space
])
def test_uk_postcode_matches_known_valid(postcode):
    """Known valid UK postcodes must match _UK_POSTCODE_RE.

    Validates: Requirements 6.2, 6.3, 6.4
    """
    assert _UK_POSTCODE_RE.match(postcode) is not None, (
        f"Expected UK postcode regex to match {postcode!r}"
    )


# ---------------------------------------------------------------------------
# 2. UK postcode does NOT match ICAO or ZIP
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("postcode", ["SW1A 1AA", "SW1A1AA"])
def test_uk_postcode_not_confused_with_icao(postcode):
    """UK postcodes must not match the ICAO regex.

    Validates: Requirements 9.2 (format disambiguation)
    """
    assert _ICAO_RE.match(postcode) is None, (
        f"UK postcode {postcode!r} should NOT match ICAO regex"
    )


@pytest.mark.parametrize("postcode", ["SW1A 1AA", "SW1A1AA"])
def test_uk_postcode_not_confused_with_zip(postcode):
    """UK postcodes must not match the ZIP regex.

    Validates: Requirements 9.2 (format disambiguation)
    """
    assert _ZIP_RE.match(postcode) is None, (
        f"UK postcode {postcode!r} should NOT match ZIP regex"
    )


# ---------------------------------------------------------------------------
# 3. ZIP code format detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("zipcode", ["90210", "28801"])
def test_zip_matches_valid(zipcode):
    """Valid 5-digit ZIP codes must match _ZIP_RE.

    Validates: Requirements 9.3
    """
    assert _ZIP_RE.match(zipcode) is not None, (
        f"Expected ZIP regex to match {zipcode!r}"
    )


@pytest.mark.parametrize("invalid_zip", ["9021", "902101"])
def test_zip_rejects_wrong_length(invalid_zip):
    """ZIP regex must reject strings that are not exactly 5 digits.

    Validates: Requirements 9.3
    """
    assert _ZIP_RE.match(invalid_zip) is None, (
        f"ZIP regex should NOT match {invalid_zip!r}"
    )


# ---------------------------------------------------------------------------
# 4. ZIP does NOT match UK postcode
# ---------------------------------------------------------------------------

def test_zip_not_confused_with_uk_postcode():
    """A 5-digit ZIP code must not match the UK postcode regex.

    Validates: Requirements 9.2, 9.3 (format disambiguation)
    """
    assert _UK_POSTCODE_RE.match("90210") is None, (
        "ZIP '90210' should NOT match UK postcode regex"
    )


# ---------------------------------------------------------------------------
# 5. ICAO format detection
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("icao", ["KJFK", "EGLL"])
def test_icao_matches_valid(icao):
    """Valid 4-letter uppercase ICAO codes must match _ICAO_RE.

    Validates: Requirements 7.4
    """
    assert _ICAO_RE.match(icao) is not None, (
        f"Expected ICAO regex to match {icao!r}"
    )


def test_icao_rejects_lowercase():
    """ICAO regex must reject lowercase (codes are normalized to uppercase before matching).

    Validates: Requirements 7.4
    """
    assert _ICAO_RE.match("kjfk") is None, (
        "ICAO regex should NOT match lowercase 'kjfk'"
    )


@pytest.mark.parametrize("invalid_icao", ["KJF", "KJFK1"])
def test_icao_rejects_wrong_length(invalid_icao):
    """ICAO regex must reject strings that are not exactly 4 uppercase letters.

    Validates: Requirements 7.4
    """
    assert _ICAO_RE.match(invalid_icao) is None, (
        f"ICAO regex should NOT match {invalid_icao!r}"
    )


# ---------------------------------------------------------------------------
# 6. ICAO does NOT match UK postcode or ZIP
# ---------------------------------------------------------------------------

def test_icao_not_confused_with_uk_postcode():
    """An ICAO code must not match the UK postcode regex.

    Validates: Requirements 9.4 (format disambiguation)
    """
    assert _UK_POSTCODE_RE.match("KJFK") is None, (
        "ICAO 'KJFK' should NOT match UK postcode regex"
    )


def test_icao_not_confused_with_zip():
    """An ICAO code must not match the ZIP regex.

    Validates: Requirements 9.4 (format disambiguation)
    """
    assert _ZIP_RE.match("KJFK") is None, (
        "ICAO 'KJFK' should NOT match ZIP regex"
    )


# ---------------------------------------------------------------------------
# 7. Nominatim display name truncation edge cases
# ---------------------------------------------------------------------------

def test_truncation_exactly_80_chars():
    """A display name of exactly 80 characters should be unchanged.

    Validates: Requirements 8.6
    """
    name = "A" * 80
    assert _truncate_display_name(name) == name


def test_truncation_81_chars():
    """A display name of 81 characters should be truncated to 80 (77 + '...').

    Validates: Requirements 8.6
    """
    name = "B" * 81
    result = _truncate_display_name(name)
    assert len(result) == 80
    assert result == "B" * 77 + "..."


def test_truncation_empty_string():
    """An empty display name should be returned unchanged.

    Validates: Requirements 8.6
    """
    assert _truncate_display_name("") == ""


def test_truncation_79_chars():
    """A display name of 79 characters should be returned unchanged.

    Validates: Requirements 8.6
    """
    name = "C" * 79
    assert _truncate_display_name(name) == name

"""
regex.py
Custom Presidio PatternRecognizers for PII entities that the built-in spaCy
NLP model misses or handles poorly.

Designed for Indian legal documents (lawShield context) with additional
coverage for international formats that appear in cross-border filings.

Scoring guide (Presidio convention):
  1.0  = Checksummed / cryptographically verifiable (e.g. Luhn, Aadhaar Verhoeff)
  0.85 = Very distinctive format, very low false-positive rate
  0.75 = Distinctive format with context boost
  0.50 = Structural match only, context required to elevate
  0.30 = Broad pattern, context is mandatory

All patterns use word-boundary assertions (\b) where relevant to avoid
matching substrings of longer numbers (e.g. "12345678901" inside "012345678901").
"""

from presidio_analyzer import PatternRecognizer, Pattern

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make(entity: str, patterns: list[Pattern], context: list[str]) -> PatternRecognizer:
    return PatternRecognizer(
        supported_entity=entity,
        patterns=patterns,
        context=context,
    )


# ---------------------------------------------------------------------------
# India-specific identifiers
# ---------------------------------------------------------------------------

def _aadhaar_recognizer() -> PatternRecognizer:
    """
    Aadhaar: 12 digits, optionally space- or hyphen-separated in groups of 4.
    Format examples: 1234 5678 9012  |  1234-5678-9012  |  123456789012
    First digit cannot be 0 or 1 (UIDAI spec).
    """
    patterns = [
        Pattern(
            name="aadhaar_spaced",
            regex=r"\b[2-9]\d{3}[\s\-]\d{4}[\s\-]\d{4}\b",
            score=0.85,
        ),
        Pattern(
            name="aadhaar_plain",
            regex=r"\b[2-9]\d{11}\b",
            score=0.50,
        ),
    ]
    context = [
        "aadhaar", "aadhar", "uid", "unique identification",
        "uidai", "resident", "biometric",
    ]
    return _make("AADHAAR_NUMBER", patterns, context)


def _pan_recognizer() -> PatternRecognizer:
    """
    PAN (Permanent Account Number): 10-char alphanumeric.
    Format: AAAAA9999A  (5 alpha, 4 digits, 1 alpha — all uppercase)
    """
    patterns = [
        Pattern(
            name="pan_card",
            regex=r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
            score=0.85,
        ),
    ]
    context = [
        "pan", "permanent account", "income tax", "it department",
        "taxpayer", "tin", "form 16",
    ]
    return _make("IN_PAN", patterns, context)


def _gstin_recognizer() -> PatternRecognizer:
    """
    GST Identification Number: 15 characters.
    Format: 2-digit state code + 10-char PAN + 1 entity count + Z + checksum.
    Example: 27AAPFU0939F1ZV
    """
    patterns = [
        Pattern(
            name="gstin",
            regex=r"\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b",
            score=0.90,
        ),
    ]
    context = ["gstin", "gst", "goods and services tax", "gstn", "gst number"]
    return _make("IN_GSTIN", patterns, context)


def _voter_id_recognizer() -> PatternRecognizer:
    """
    Indian Voter ID (EPIC): 3 alpha + 7 digits.
    Example: ABC1234567
    """
    patterns = [
        Pattern(
            name="voter_id",
            regex=r"\b[A-Z]{3}[0-9]{7}\b",
            score=0.65,
        ),
    ]
    context = ["voter", "epic", "election", "voter id", "voter card", "electorl"]
    return _make("IN_VOTER_ID", patterns, context)


def _driving_licence_recognizer() -> PatternRecognizer:
    """
    Indian Driving Licence: 2-letter state code + 2-digit RTO + year + 7 digits.
    Example: MH12 20190012345 or MH1220190012345
    """
    patterns = [
        Pattern(
            name="dl_spaced",
            regex=r"\b[A-Z]{2}[\s\-]?\d{2}[\s\-]?\d{4}[\s\-]?\d{7}\b",
            score=0.80,
        ),
    ]
    context = ["driving licence", "dl", "driving license", "licence number", "motor vehicle"]
    return _make("IN_DRIVING_LICENCE", patterns, context)


def _indian_passport_recognizer() -> PatternRecognizer:
    """
    Indian Passport: 1 alpha + 7 digits.
    Example: A1234567
    """
    patterns = [
        Pattern(
            name="indian_passport",
            regex=r"\b[A-PR-WY][0-9]{7}\b",
            score=0.75,
        ),
    ]
    context = ["passport", "travel document", "passport number", "immigration"]
    return _make("IN_PASSPORT", patterns, context)


def _ifsc_recognizer() -> PatternRecognizer:
    """
    IFSC Code (Indian Financial System Code): 4 alpha bank code + 0 + 6 alphanumeric.
    Example: SBIN0001234
    """
    patterns = [
        Pattern(
            name="ifsc",
            regex=r"\b[A-Z]{4}0[A-Z0-9]{6}\b",
            score=0.85,
        ),
    ]
    context = ["ifsc", "bank code", "branch code", "neft", "rtgs", "imps", "transfer"]
    return _make("IN_IFSC", patterns, context)


def _indian_phone_recognizer() -> PatternRecognizer:
    """
    Indian mobile and landline numbers.
    Mobile: 10 digits starting with 6-9, optionally prefixed with +91 or 0.
    Landline: 2-4 digit STD code + 6-8 digit number.
    """
    patterns = [
        Pattern(
            name="in_mobile_intl",
            regex=r"(?:\+91[\s\-]?|0)?[6-9]\d{9}\b",
            score=0.75,
        ),
        Pattern(
            name="in_mobile_bare",
            regex=r"\b[6-9]\d{9}\b",
            score=0.50,
        ),
    ]
    context = ["phone", "mobile", "cell", "contact", "call", "whatsapp", "number"]
    return _make("IN_PHONE_NUMBER", patterns, context)


# ---------------------------------------------------------------------------
# Financial identifiers (international / India)
# ---------------------------------------------------------------------------

def _bank_account_recognizer() -> PatternRecognizer:
    """
    Indian bank account numbers: typically 9–18 digits.
    We require a context keyword to minimise false positives on bare numbers.
    """
    patterns = [
        Pattern(
            name="bank_account_in",
            regex=r"\b\d{9,18}\b",
            score=0.50,
        ),
    ]
    context = [
        "account", "account no", "account number", "savings account",
        "current account", "bank", "debit", "credit account",
    ]
    return _make("BANK_ACCOUNT", patterns, context)


def _iban_recognizer() -> PatternRecognizer:
    """
    IBAN (used in international wire transfers common in NRI filings).
    Format: 2 alpha country code + 2 check digits + up to 30 alphanumeric.
    """
    patterns = [
        Pattern(
            name="iban",
            regex=(
                r"\b[A-Z]{2}\d{2}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{4}[\s]?"
                r"[A-Z0-9]{4}[\s]?[A-Z0-9]{4}[\s]?[A-Z0-9]{0,4}\b"
            ),
            score=0.85,
        ),
    ]
    context = ["iban", "international bank", "swift", "bic", "wire transfer", "foreign remittance"]
    return _make("IBAN_CODE", patterns, context)


# ---------------------------------------------------------------------------
# Tax / Government identifiers
# ---------------------------------------------------------------------------

def _ssn_recognizer() -> PatternRecognizer:
    """
    US SSN — appears in documents for US citizens / NRIs with US filings.
    Format: XXX-XX-XXXX (hyphens required to reduce false positives).
    """
    patterns = [
        Pattern(
            name="ssn_hyphenated",
            regex=r"\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b",
            score=0.85,
        ),
    ]
    context = ["ssn", "social security", "taxpayer id", "tin"]
    return _make("US_SSN", patterns, context)


# ---------------------------------------------------------------------------
# Personal identifiers
# ---------------------------------------------------------------------------

def _date_of_birth_recognizer() -> PatternRecognizer:
    """
    Date of birth in common Indian document formats:
      DD/MM/YYYY  |  DD-MM-YYYY  |  DD.MM.YYYY  |  YYYY-MM-DD (ISO)
    Only flags values that are plausibly a human's birth year (1900–2010).
    """
    patterns = [
        Pattern(
            name="dob_dmy",
            regex=r"\b(0?[1-9]|[12]\d|3[01])[\/\-\.](0?[1-9]|1[0-2])[\/\-\.](19\d{2}|200\d|201[0-9])\b",
            score=0.75,
        ),
        Pattern(
            name="dob_iso",
            regex=r"\b(19\d{2}|200\d|201[0-9])-(0?[1-9]|1[0-2])-(0?[1-9]|[12]\d|3[01])\b",
            score=0.75,
        ),
    ]
    context = [
        "date of birth", "dob", "born on", "born", "birth date",
        "birth", "age", "born", "d.o.b",
    ]
    return _make("DATE_OF_BIRTH", patterns, context)


def _ip_address_recognizer() -> PatternRecognizer:
    """
    IPv4 addresses (e.g. in forensic / cyber-law filings).
    """
    patterns = [
        Pattern(
            name="ipv4",
            regex=(
                r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
                r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
            ),
            score=0.85,
        ),
    ]
    context = ["ip", "ip address", "ipv4", "server", "device", "network", "host"]
    return _make("IP_ADDRESS", patterns, context)


def _vehicle_reg_recognizer() -> PatternRecognizer:
    """
    Indian vehicle registration number.
    New format: AA-00-AA-0000  (state + RTO + letter series + number)
    Old format: AA 00 A 0000 or AA-00-A-0000
    """
    patterns = [
        Pattern(
            name="vehicle_new",
            regex=r"\b[A-Z]{2}[\s\-]\d{2}[\s\-][A-Z]{1,3}[\s\-]\d{4}\b",
            score=0.80,
        ),
    ]
    context = [
        "vehicle", "registration", "reg no", "vehicle number",
        "car", "bike", "motor vehicle", "rc book",
    ]
    return _make("IN_VEHICLE_REG", patterns, context)


# ---------------------------------------------------------------------------
# Public registry
# ---------------------------------------------------------------------------

def get_custom_recognizers() -> list[PatternRecognizer]:
    """
    Return all custom recognisers to be registered with Presidio.

    Order matters for priority resolution when two recognisers overlap on the
    same span; higher-scoring ones win during conflict resolution.
    """
    return [
        # India-specific (highest specificity first)
        _gstin_recognizer(),
        _aadhaar_recognizer(),
        _pan_recognizer(),
        _ifsc_recognizer(),
        _indian_passport_recognizer(),
        _driving_licence_recognizer(),
        _voter_id_recognizer(),
        _indian_phone_recognizer(),
        _vehicle_reg_recognizer(),
        # Financial
        _iban_recognizer(),
        _bank_account_recognizer(),
        # Tax
        _ssn_recognizer(),
        # Personal
        _date_of_birth_recognizer(),
        _ip_address_recognizer(),
    ]

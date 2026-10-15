"""
ner.py
Presidio AnalyzerEngine setup with thread-safe lazy initialisation and a
curated entity list designed for Indian legal documents.
"""
from __future__ import annotations

import logging
import threading
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider

from .regex import get_custom_recognizers

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thread-safe lazy singleton
# ---------------------------------------------------------------------------

_analyzer: AnalyzerEngine | None = None
_analyzer_lock = threading.Lock()


def get_analyzer() -> AnalyzerEngine:
    """
    Return a shared :class:`AnalyzerEngine` instance.

    Thread-safe double-checked locking ensures the engine is initialised
    exactly once, even under concurrent FastAPI requests.
    """
    global _analyzer
    if _analyzer is None:
        with _analyzer_lock:
            if _analyzer is None:
                _analyzer = _build_analyzer()
    return _analyzer


def _build_analyzer() -> AnalyzerEngine:
    """Construct and configure the AnalyzerEngine."""
    logger.info("Initialising Presidio AnalyzerEngine…")

    # Use the large spaCy model if already downloaded; fall back to the small
    # model so the service starts even if en_core_web_lg is missing.
    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
    }
    try:
        provider = NlpEngineProvider(nlp_configuration=nlp_config)
        nlp_engine = provider.create_engine()
        logger.info("Using spaCy model: en_core_web_lg")
    except Exception:
        # Fallback: let Presidio choose the default (en_core_web_sm / transformers)
        logger.warning(
            "en_core_web_lg not available — falling back to default NLP engine."
        )
        nlp_engine = None  # type: ignore[assignment]

    registry = RecognizerRegistry()
    registry.load_predefined_recognizers(languages=["en"])

    # Register all custom recognisers
    for recognizer in get_custom_recognizers():
        registry.add_recognizer(recognizer)
        logger.debug("Registered custom recogniser: %s", recognizer.supported_entities)

    kwargs: dict = {"registry": registry}
    if nlp_engine is not None:
        kwargs["nlp_engine"] = nlp_engine

    engine = AnalyzerEngine(**kwargs)
    logger.info("AnalyzerEngine ready with %d recognisers.", len(registry.recognizers))
    return engine


# ---------------------------------------------------------------------------
# Entity catalogue
# ---------------------------------------------------------------------------

# Presidio built-in entities covered by the spaCy / rule-based recognisers
_BUILTIN_ENTITIES = [
    "PERSON",           # People's names (client, judge, witness, opponent)
    "EMAIL_ADDRESS",    # Email addresses
    "PHONE_NUMBER",     # Generic international phone numbers
    "CREDIT_CARD",      # Credit / debit card numbers (Luhn-validated)
    "ORGANIZATION",     # Law firms, companies, banks
    "LOCATION",         # Addresses, cities, states
    "DATE_TIME",        # Dates that could help re-identify (e.g. hearing dates alongside names)
    "URL",              # Web URLs that might contain personal paths
    "US_PASSPORT",      # Built-in US passport recogniser (complements IN_PASSPORT)
    "US_DRIVER_LICENSE",# US DL (NRI clients)
    "NRP",              # Nationality / religious / political group (sensitive in legal docs)
    "MEDICAL_LICENSE",  # Doctor / medical professional identifiers
    "IBAN_CODE",        # International bank account (built-in, complemented by our custom one)
    "IP_ADDRESS",       # Built-in IPv4/IPv6 recogniser
]

# Our custom entities registered above
_CUSTOM_ENTITIES = [
    "AADHAAR_NUMBER",   # 12-digit UID
    "IN_PAN",           # Permanent Account Number
    "IN_GSTIN",         # GST Identification Number
    "IN_VOTER_ID",      # Electoral Photo ID Card
    "IN_DRIVING_LICENCE",
    "IN_PASSPORT",      # Indian passport (letter + 7 digits)
    "IN_IFSC",          # Bank branch code
    "IN_PHONE_NUMBER",  # Indian mobile / STD numbers
    "IN_VEHICLE_REG",   # Registration plate
    "BANK_ACCOUNT",     # Account numbers (context-gated)
    "US_SSN",           # SSN for NRI / US-filing documents
    "DATE_OF_BIRTH",    # DOB in common Indian formats
]

# Combined list passed to every analyze() call
SUPPORTED_ENTITIES: list[str] = _BUILTIN_ENTITIES + _CUSTOM_ENTITIES

# Minimum confidence threshold — results below this are discarded even if
# Presidio returns them.  Raising this reduces false positives at the cost of
# potentially missing low-confidence matches.
CONFIDENCE_THRESHOLD: float = 0.35

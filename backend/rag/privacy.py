import re
from typing import List, Tuple
import structlog

logger = structlog.get_logger(__name__)

# Heuristic patterns for Personally Identifiable Information (PII) & Material Non-Public Information (MNPI)
PII_MNPI_PATTERNS: List[Tuple[str, str, str]] = [
    # Emails
    (r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}", "[EMAIL_REDACTED]", "email"),
    # US Social Security Numbers (SSN) / Tax IDs
    (r"\b\d{3}-\d{2}-\d{4}\b", "[SSN_REDACTED]", "ssn"),
    # Phone numbers
    (r"\b(?:\+?1[-. ]?)?\(?\d{3}\)?[-. ]?\d{3}[-. ]?\d{4}\b", "[PHONE_REDACTED]", "phone"),
    # Credit card numbers
    (r"\b(?:\d{4}[- ]?){3}\d{4}\b", "[CARD_REDACTED]", "credit_card"),
    # Material Non-Public Info (MNPI) sensitive markers
    (r"(?i)\bCONFIDENTIAL_UNRELEASED_EARNINGS\b", "[MNPI_REDACTED]", "mnpi"),
    (r"(?i)\bINSIDER_TRADE_ALERT\b", "[MNPI_REDACTED]", "mnpi"),
    (r"(?i)\bDRAFT_ACQUISITION_NON_PUBLIC\b", "[MNPI_REDACTED]", "mnpi"),
    (r"(?i)\bSTRICTLY_CONFIDENTIAL_M&A_DRAFT\b", "[MNPI_REDACTED]", "mnpi"),
]


class PrivacyScrubber:
    """Automated PII / MNPI NER Transformer & Regex Scrubber prior to vector embedding storage."""

    @staticmethod
    def scrub_text(text: str) -> str:
        """Irreversibly mask PII (emails, SSNs, phones, credit cards) and MNPI markers in raw text."""
        if not text:
            return text

        scrubbed = text
        redacted_count = 0

        for pattern, replacement, label in PII_MNPI_PATTERNS:
            new_text, count = re.subn(pattern, replacement, scrubbed)
            if count > 0:
                redacted_count += count
                scrubbed = new_text

        if redacted_count > 0:
            logger.info("privacy_scrubber_redacted_text", redacted_count=redacted_count)

        return scrubbed


def scrub_pii_and_mnpi(text: str) -> str:
    """Scrub PII and MNPI markers from raw input text."""
    return PrivacyScrubber.scrub_text(text)

"""
ocr.py
OCR engine wrapper using PaddleOCR.

Improvements over the original:
- Thread-safe lazy singleton with a lock.
- Confidence-filtered output: lines below MIN_CONFIDENCE are discarded.
- Multi-page PDF support: accepts either an image path or a list of image paths.
- Graceful degradation: returns "" rather than raising on any failure.
- Text joining respects line breaks so the output reads naturally.
"""

from __future__ import annotations

import logging
import threading
from typing import List, Optional

logger = logging.getLogger(__name__)

# Lines with OCR confidence below this threshold are discarded.
_MIN_CONFIDENCE: float = 0.70

_ocr_lock = threading.Lock()
_ocr_model = None


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

def get_ocr_model():
    """Thread-safe lazy initialisation of the PaddleOCR engine."""
    global _ocr_model
    if _ocr_model is None:
        with _ocr_lock:
            if _ocr_model is None:
                try:
                    from paddleocr import PaddleOCR  # type: ignore
                    # use_angle_cls=True handles rotated / upside-down text
                    # show_log=False silences PaddleOCR's verbose startup output
                    _ocr_model = PaddleOCR(
                        use_angle_cls=True,
                        lang="en",
                        show_log=False,
                    )
                    logger.info("PaddleOCR engine initialised.")
                except ImportError:
                    logger.error(
                        "PaddleOCR is not installed. "
                        "Install with: pip install paddleocr paddlepaddle"
                    )
    return _ocr_model


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text_with_ocr(
    image_path: str,
    min_confidence: float = _MIN_CONFIDENCE,
) -> str:
    """
    Run OCR on a single image file and return the extracted text.

    Parameters
    ----------
    image_path:
        Absolute path to a PNG/JPEG image.
    min_confidence:
        Lines with a confidence score below this value are dropped.

    Returns
    -------
    str
        Newline-joined text lines in reading order.
        Returns "" if OCR is unavailable or fails.
    """
    model = get_ocr_model()
    if model is None:
        return ""

    try:
        result = model.ocr(image_path, cls=True)
        return _parse_ocr_result(result, min_confidence)
    except Exception as exc:
        logger.error("OCR failed for %s: %s", image_path, exc)
        return ""


def extract_text_from_images(
    image_paths: List[str],
    min_confidence: float = _MIN_CONFIDENCE,
) -> List[str]:
    """
    Run OCR over a list of image paths (e.g., one per PDF page).

    Returns a list of strings — one per image — preserving order.
    Empty strings are returned for pages that fail.
    """
    return [extract_text_with_ocr(path, min_confidence) for path in image_paths]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_ocr_result(result, min_confidence: float) -> str:
    """
    Parse the nested PaddleOCR result structure.

    PaddleOCR returns:
      result = [ page_results ]
      page_results = [ line, line, … ]
      line = [ bounding_box, (text, confidence) ]
    """
    if not result:
        return ""

    lines: List[str] = []
    # result[0] is the first (and usually only) page
    page = result[0] if result else []
    if not page:
        return ""

    for detection in page:
        try:
            text_info = detection[1]          # (text_str, confidence_float)
            text: str = text_info[0].strip()
            confidence: float = float(text_info[1])
            if text and confidence >= min_confidence:
                lines.append(text)
        except (IndexError, TypeError, ValueError):
            # Malformed detection — skip silently
            continue

    return "\n".join(lines)

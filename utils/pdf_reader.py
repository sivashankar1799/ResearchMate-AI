"""
pdf_reader.py
Handles PDF validation and text extraction using PyMuPDF (fitz).
Single-responsibility functions for opening, validating and extracting.
"""

import fitz  # PyMuPDF


def validate_pdf(path):
    """
    Return True if the file at `path` can be opened by PyMuPDF as a PDF.
    Used to reject corrupt or mislabeled files.
    """
    try:
        with fitz.open(path) as doc:
            # A valid PDF should report a non-negative page count
            return doc.page_count >= 0
    except Exception:
        return False


def extract_pdf_text(path):
    """
    Extract the full text from a PDF.

    Returns:
        (text, page_count, word_count)
    """
    full_text_parts = []
    page_count = 0

    with fitz.open(path) as doc:
        page_count = doc.page_count
        for page in doc:
            # "text" mode gives a clean linear text extraction
            page_text = page.get_text("text")
            if page_text:
                full_text_parts.append(page_text)

    text = "\n".join(full_text_parts).strip()
    # Word count from whitespace-split tokens
    word_count = len(text.split()) if text else 0
    return text, page_count, word_count


def get_page_texts(path):
    """
    Return a list of per-page text strings.
    Useful for chunked/section-aware processing.
    """
    pages = []
    with fitz.open(path) as doc:
        for page in doc:
            pages.append(page.get_text("text"))
    return pages
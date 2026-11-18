"""
pdf_checks.py

Checks that an uploaded file really is a PDF we can work with.
This runs before any signing or verification, so that broken or
unexpected files are rejected with a clear message.
"""

import io

from pyhanko.pdf_utils.reader import PdfFileReader


MAXIMUM_PDF_SIZE_IN_BYTES = 25 * 1024 * 1024


def check_pdf_bytes(pdf_bytes):
    # Raise a ValueError with a friendly message if the file is not usable.
    if len(pdf_bytes) == 0:
        raise ValueError("The file is empty.")

    if len(pdf_bytes) > MAXIMUM_PDF_SIZE_IN_BYTES:
        raise ValueError("The file is larger than 25 MB.")

    # Every real PDF starts with the text "%PDF-" near the beginning.
    start_of_file = pdf_bytes[:1024]

    if b"%PDF-" not in start_of_file:
        raise ValueError("This file is not a PDF document.")

    # Try to read the PDF structure. A damaged PDF can fail in many different
    # ways, so every kind of error is turned into the same friendly message.
    try:
        pdf_reader = PdfFileReader(io.BytesIO(pdf_bytes))
        pdf_is_encrypted = pdf_reader.encrypted
    except Exception:
        raise ValueError("The PDF could not be read. The file may be damaged.")

    if pdf_is_encrypted:
        raise ValueError("Password-protected PDFs are not supported.")

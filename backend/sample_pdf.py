"""
sample_pdf.py

Builds a tiny but valid one-page PDF by hand, using plain (uncompressed) text.
It is used by demo.py and test_app.py, which keeps them free of extra
dependencies and lets them tamper with the visible text on purpose.
"""


def build_sample_pdf(text_lines):
    # Build a tiny but valid one-page PDF by hand, with plain (uncompressed) text.
    # This keeps the demo free of extra dependencies and lets us tamper with
    # the visible text later.
    text_commands = ["BT", "/F1 18 Tf", "72 720 Td", "24 TL"]

    for line in text_lines:
        text_commands.append("(" + line + ") Tj T*")

    text_commands.append("ET")
    page_content = "\n".join(text_commands).encode("latin-1")

    pdf_objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length " + str(len(page_content)).encode() + b" >>\nstream\n" + page_content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf_bytes = b"%PDF-1.7\n"
    object_offsets = []

    for object_number, object_body in enumerate(pdf_objects, start=1):
        object_offsets.append(len(pdf_bytes))
        pdf_bytes += str(object_number).encode() + b" 0 obj\n" + object_body + b"\nendobj\n"

    xref_offset = len(pdf_bytes)
    pdf_bytes += b"xref\n0 " + str(len(pdf_objects) + 1).encode() + b"\n"
    pdf_bytes += b"0000000000 65535 f \n"

    for offset in object_offsets:
        pdf_bytes += str(offset).zfill(10).encode() + b" 00000 n \n"

    pdf_bytes += b"trailer\n<< /Size " + str(len(pdf_objects) + 1).encode() + b" /Root 1 0 R >>\n"
    pdf_bytes += b"startxref\n" + str(xref_offset).encode() + b"\n%%EOF\n"

    return pdf_bytes

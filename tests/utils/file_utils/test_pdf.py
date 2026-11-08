from unittest.mock import MagicMock, patch

import pytest

from utils.file_utils.pdf import read_pdf_pages


def test_reads_real_pdf_text_and_blank_page(tmp_path):
    content = b"BT /F1 12 Tf 72 720 Td (Invoice 123) Tj 0 -16 Td (Total 42.50) Tj ET"
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R 6 0 R] /Count 2 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(content)).encode() + b" >>\nstream\n" + content + b"\nendstream",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{index} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(offsets)}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010d} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path = tmp_path / "invoice.pdf"
    path.write_bytes(data)
    assert read_pdf_pages(path) == ["Invoice 123\nTotal 42.50", ""]


def test_closes_native_handles_when_extraction_fails():
    document = MagicMock()
    document.__len__.return_value = 1
    page = document.__getitem__.return_value
    textpage = page.get_textpage.return_value
    textpage.get_text_bounded.side_effect = RuntimeError("Extraction failed")
    with patch("utils.file_utils.pdf.pypdfium2.PdfDocument") as constructor:
        constructor.return_value.__enter__.return_value = document
        with pytest.raises(RuntimeError, match="Extraction failed"):
            read_pdf_pages("invoice.pdf")
    textpage.close.assert_called_once()
    page.close.assert_called_once()
    constructor.return_value.__exit__.assert_called_once()

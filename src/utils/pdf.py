"""Text extraction shared by supplier PDF parsers."""
from pathlib import Path

import pypdfium2

__all__ = ["read_pdf_pages"]


def read_pdf_pages(path: str | Path) -> list[str]:
    """Extract page text with normalized newlines and close native handles."""
    pages = []
    with pypdfium2.PdfDocument(path) as document:
        for index in range(len(document)):
            page = document[index]
            try:
                textpage = page.get_textpage()
                try:
                    pages.append(textpage.get_text_bounded().replace("\r\n", "\n"))
                finally:
                    textpage.close()
            finally:
                page.close()
    return pages

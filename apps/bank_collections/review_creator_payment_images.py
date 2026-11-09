#!/usr/bin/env python3
"""Download Creator payment images and cross-check local Tesseract OCR evidence."""
from __future__ import annotations
import argparse
import importlib
from collections.abc import Mapping
from pathlib import Path

if __package__:
    from . import _bootstrap
else:
    importlib.import_module("_bootstrap")

from workflows.runtime.auth import get_creator_client
from workflows.creator_payments.ocr import PaymentOCRSource, review_creator_payment_images


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--creator-app", default="order-management-new")
    parser.add_argument("--online-report", default="Online_Payments")
    parser.add_argument("--cheque-report", default="Cheques")
    parser.add_argument("--image-field", default="Payment_Image")
    parser.add_argument("--criteria", help="Creator criteria applied to both reports")
    parser.add_argument("--limit", type=int, help="Maximum records per report")
    parser.add_argument("--output-dir", type=Path, default=Path("output/creator_payment_ocr"))
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    import shutil
    import importlib.util
    if not shutil.which("tesseract") or any(importlib.util.find_spec(m) is None for m in ("PIL", "pytesseract")):
        parser.error("Install WOA[ocr] and the Tesseract executable before running OCR.")
    result = review_creator_payment_images(
        get_creator_client(), app=args.creator_app,
        sources=(PaymentOCRSource(args.online_report, args.image_field),
                 PaymentOCRSource(args.cheque_report, args.image_field, date_field="Cheque_Date")),
        output_dir=args.output_dir, criteria=args.criteria, limit=args.limit,
    )
    summary = result.get("summary")
    summary_dict = summary if isinstance(summary, Mapping) else {}
    print("| Status | Records |\n| --- | ---: |")
    for status, count in summary_dict.items():
        print(f"| {status} | {count} |")
    print(f"Review: {(args.output_dir / 'review.md').resolve()}")
    return 1 if summary_dict.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())

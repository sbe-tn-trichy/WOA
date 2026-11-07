"""Unit tests for the unified CLI dispatchers (Phase 2 consolidation)."""
from unittest.mock import patch

import pytest

from apps import inter_location, neoseal, verify_gst


def test_neoseal_help_and_unknown(capsys):
    assert neoseal.main(["--help"]) == 0
    captured = capsys.readouterr()
    assert "usage: neoseal.py" in captured.out
    assert "audit" in captured.out

    assert neoseal.main(["nonexistent-command"]) == 2
    captured = capsys.readouterr()
    assert "Unknown command" in captured.err


def test_neoseal_subcommand_dispatch():
    with patch("apps.audit_neoseal_items.main", return_value=0) as mock_main:
        assert neoseal.main(["audit", "--help"]) == 0
        mock_main.assert_called_once_with(["--help"])


def test_verify_gst_help_and_unknown(capsys):
    assert verify_gst.main(["--help"]) == 0
    captured = capsys.readouterr()
    assert "usage: verify_gst.py" in captured.out
    assert "gstr1" in captured.out

    assert verify_gst.main(["nonexistent-command"]) == 2
    captured = capsys.readouterr()
    assert "Unknown command" in captured.err


def test_verify_gst_subcommand_dispatch():
    with patch("apps.verify_gstr1.main", return_value=0) as mock_main:
        assert verify_gst.main(["gstr1"]) == 0
        mock_main.assert_called_once()


def test_inter_location_help_and_unknown(capsys):
    assert inter_location.main(["--help"]) == 0
    captured = capsys.readouterr()
    assert "usage: inter_location.py" in captured.out
    assert "contra" in captured.out

    assert inter_location.main(["nonexistent-command"]) == 2
    captured = capsys.readouterr()
    assert "Unknown command" in captured.err


def test_inter_location_subcommand_dispatch():
    with patch("apps.review_inter_location_contra.main", return_value=0) as mock_main:
        assert inter_location.main(["contra", "--help"]) == 0
        mock_main.assert_called_once_with(["--help"])

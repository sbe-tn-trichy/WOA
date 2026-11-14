from utils.file_utils import json
from apps.payments import post_creator_cash_transfer as cli
from workflows.creator_payments import CashTransferResult


def test_cli_prints_structured_preview_and_does_not_apply(monkeypatch, capsys):
    monkeypatch.setattr(cli, "get_books_client", lambda: object())
    monkeypatch.setattr(cli, "get_creator_client", lambda: object())
    def preview(books, creator, **kwargs):
        assert kwargs["transfer_id"] == "1" and kwargs["location_id"] == "2"
        assert kwargs["apply"] is False
        return CashTransferResult("PREVIEW", "report.json", ("3", "4"), "")
    monkeypatch.setattr(cli, "post_cash_transfer", preview)
    assert cli.main(["--transfer-id", "1", "--location-id", "2"]) == 0
    assert json.loads(capsys.readouterr().out)["payment_ids"] == ["3", "4"]


def test_cli_reports_failures_without_claiming_success(monkeypatch, capsys):
    def failure():
        raise RuntimeError("token unavailable")
    monkeypatch.setattr(cli, "get_books_client", failure)
    assert cli.main(["--transfer-id", "1", "--location-id", "2"]) == 1
    output = capsys.readouterr()
    assert not output.out and "token unavailable" in output.err

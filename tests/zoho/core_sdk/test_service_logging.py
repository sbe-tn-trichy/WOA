from unittest.mock import Mock, call, patch

import pytest

from zoho.core_sdk.base_client import BaseZohoClient
from zoho.core_sdk.logging import configure_service_logger


@pytest.mark.parametrize(("service", "configs"), [
    ("books", [("zoho.books.api", "zoho_books_api.log"), ("zoho_books", "zoho_books_api.log")]),
    ("inventory", [("zoho_inventory", "zoho_inventory_api.log")]),
    ("wd", [("zoho.wd.api", "zoho_wd_api.log"), ("zoho.wd.app", "app.log"), ("zoho_wd.app", "app.log")]),
    ("mail", [("zoho_mail", "zoho_mail_api.log")]),
    ("sheet", [("zoho_sheet", "zoho_sheet_api.log")]),
    ("creator", [("zoho_creator", "zoho_creator_api.log")]),
    ("cliq", [("zoho_cliq", "zoho_cliq_api.log")]),
])
def test_service_logger_preserves_configuration(service, configs):
    primary = Mock()
    with patch("zoho.core_sdk.logging.configure_logger", side_effect=[primary] + [Mock() for _ in configs[1:]]) as configure:
        assert configure_service_logger(service) is primary
    assert configure.call_args_list == [call(*config) for config in configs]


@pytest.mark.parametrize("service", ["analytics", "erp", "unknown", ""])
def test_unknown_service_uses_named_logger(service):
    with patch("zoho.core_sdk.logging.configure_logger") as configure, patch("zoho.core_sdk.logging.logging.getLogger") as get_logger:
        assert configure_service_logger(service) is get_logger.return_value
    get_logger.assert_called_once_with(f"zoho.{service}")
    configure.assert_not_called()


def test_base_client_delegates_logger_setup():
    with patch("zoho.core_sdk.base_client.configure_service_logger") as configure:
        with BaseZohoClient("token", "in", "https://example.invalid", "books") as client:
            assert client.logger is configure.return_value
    configure.assert_called_once_with("books")

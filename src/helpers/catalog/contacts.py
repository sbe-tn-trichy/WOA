"""Higher-level helper functions for Zoho Books contact operations."""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from zoho.core_sdk.validation import require_records, require_text
from ..formatting.gst import normalize_gstin, is_valid_gstin
from ..operations.records import AmbiguousMatchError, SearchResource, distinct_records, unique_record
from .custom_fields import get_custom_field_value

logger = logging.getLogger("helpers.catalog.contacts")


class _CustomerSearchClient(Protocol):
    @property
    def contacts(self) -> SearchResource: ...


@dataclass(frozen=True)
class CustomerSearchResult:
    """Distinct matching customers from a completed search."""

    candidates: tuple[dict[str, object], ...]

    @property
    def status(self) -> Literal["no_match", "unique", "ambiguous"]:
        if not self.candidates:
            return "no_match"
        return "unique" if len(self.candidates) == 1 else "ambiguous"


def _phone_digits(value: object) -> str:
    return re.sub(r"[\s()+.-]", "", str(value or ""))


def search_customers(
    books_client: _CustomerSearchClient,
    query: str,
    *,
    by: Literal["name", "gstin", "phone"] = "name",
    exact: bool = True,
) -> CustomerSearchResult:
    """Search Books customers by name, GSTIN, or the contact's phone/mobile."""
    cleaned = query.strip()
    if not cleaned:
        raise ValueError("Customer search query is required")
    if by == "name":
        target = cleaned.casefold()
        suffix = "" if exact else "_contains"
        filters = [{f"{field}{suffix}": cleaned} for field in ("contact_name", "company_name")]
    elif by == "gstin":
        target = normalize_gstin(cleaned)
        if not is_valid_gstin(target):
            raise ValueError("Customer search requires a valid GSTIN")
        filters = [{}]
    elif by == "phone":
        target = _phone_digits(cleaned)
        if not target.isascii() or not target.isdigit():
            raise ValueError("Customer search requires a valid phone number")
        filters = [{}]
    else:
        raise ValueError(f"Unsupported customer search field: {by}")

    matches: list[dict[str, object]] = []
    for search_filter in filters:
        rows = require_records(
            books_client.contacts.list_all(
                params={"contact_type": "customer", **search_filter}, resource_key="contacts",
            ),
            "Books customer search",
        )
        for row in rows:
            if row.get("contact_type") != "customer":
                if row.get("contact_type") == "vendor":
                    continue
                raise ValueError("Books customer search returned an unknown contact type")
            if by == "name":
                names = [str(row.get(key) or "").strip().casefold()
                         for key in ("contact_name", "company_name")]
                matched = target in names if exact else any(target in name for name in names)
            elif by == "gstin":
                matched = any(target == normalize_gstin(value) for value in (
                    row.get("gst_no"), row.get("gstin"),
                    get_custom_field_value(row, "gstin"), get_custom_field_value(row, "gst_no"),
                ))
            else:
                matched = any(target == _phone_digits(row.get(key)) for key in ("phone", "mobile"))
            if matched:
                matches.append(row)
    return CustomerSearchResult(tuple(distinct_records(matches, "contact_id")))


class BooksContactsResource(Protocol):
    def list(self, params: dict[str, object] | None = None) -> object: ...
    def list_all(
        self, params: dict[str, object] | None = None, resource_key: str | None = None,
    ) -> object: ...


class BooksContactsClient(Protocol):
    contacts: BooksContactsResource


def _get_contacts_iterable(contacts_resource: object, params: dict[str, object]) -> object:
    """Safely obtain iterable over contacts supporting list_all, list_iter, or list."""
    if hasattr(contacts_resource, "list_all") and callable(getattr(contacts_resource, "list_all")):
        res = getattr(contacts_resource, "list_all")(params=params, resource_key="contacts")
        if isinstance(res, list):
            return res
    if hasattr(contacts_resource, "list_iter") and callable(getattr(contacts_resource, "list_iter")):
        res = getattr(contacts_resource, "list_iter")(params=params, resource_key="contacts")
        if isinstance(res, (list, tuple)) or hasattr(res, "__iter__"):
            return res
    if hasattr(contacts_resource, "list") and callable(getattr(contacts_resource, "list")):
        res = getattr(contacts_resource, "list")(params=params)
        if isinstance(res, dict):
            return res.get("contacts", [])
        if isinstance(res, list):
            return res
    return []


def find_contact_by_gstin(
    books_client: BooksContactsClient,
    gstin: str,
    contact_type: str | None = None,
) -> dict[str, object] | None:
    """Look up a contact by their GSTIN (tax identifier).

    Performs case-insensitive matching against `gst_no` and custom fields.
    """
    cleaned_gstin = str(gstin or "").strip().upper()
    if not cleaned_gstin:
        return None

    params: dict[str, object] = {}
    if contact_type:
        params["contact_type"] = contact_type

    try:
        contacts = _get_contacts_iterable(books_client.contacts, params)
        if isinstance(contacts, (list, tuple)):
            for contact in contacts:
                if not isinstance(contact, Mapping):
                    continue
                c_gst = str(contact.get("gst_no") or contact.get("gstin") or "").strip().upper()
                if c_gst == cleaned_gstin:
                    return dict(contact)
                # Check custom field if GSTIN stored in custom fields
                cf_gst = get_custom_field_value(contact, "gstin") or get_custom_field_value(contact, "gst_no")
                if cf_gst and str(cf_gst).strip().upper() == cleaned_gstin:
                    return dict(contact)
    except Exception as exc:
        logger.warning(f"Error querying contacts by GSTIN {cleaned_gstin}: {exc}")
        return None

    return None


def find_contact_by_name(
    books_client: BooksContactsClient,
    contact_name: str,
    contact_type: str | None = None,
    exact: bool = True,
) -> dict[str, object] | None:
    """Look up a contact by contact_name or company_name."""
    name_cleaned = str(contact_name or "").strip()
    if not name_cleaned:
        return None

    target = name_cleaned.lower()
    params: dict[str, object] = {"contact_name": name_cleaned}
    if contact_type:
        params["contact_type"] = contact_type

    try:
        res = books_client.contacts.list(params=params)
        contacts = res.get("contacts", []) if isinstance(res, dict) else (res if isinstance(res, list) else [])
        for contact in contacts:
            if not isinstance(contact, Mapping):
                continue
            c_name = str(contact.get("contact_name") or "").strip().lower()
            c_company = str(contact.get("company_name") or "").strip().lower()
            if exact:
                if c_name == target or c_company == target:
                    return dict(contact)
            else:
                if target in c_name or target in c_company:
                    return dict(contact)
    except Exception as exc:
        logger.warning(f"Error searching contacts by name '{name_cleaned}': {exc}")

    return None


def fetch_active_customers_map(
    books_client: BooksContactsClient,
    key_field: str = "contact_id",
    status: str = "active",
) -> dict[str, dict[str, object]]:
    """Fetch all customers from Zoho Books and return an indexed dictionary.

    Keys are extracted from either direct attributes or custom fields using `key_field`.
    """
    params: dict[str, object] = {
        "contact_type": "customer",
        "status": status,
    }
    customer_map: dict[str, dict[str, object]] = {}

    try:
        contacts = _get_contacts_iterable(books_client.contacts, params)
        if isinstance(contacts, (list, tuple)):
            for contact in contacts:
                if not isinstance(contact, Mapping):
                    continue
                key_val = contact.get(key_field)
                if key_val is None:
                    key_val = get_custom_field_value(contact, key_field)

                if key_val is not None:
                    clean_key = str(key_val).strip()
                    if clean_key:
                        customer_map[clean_key] = dict(contact)
    except Exception as exc:
        logger.error(f"Error building customer map with key '{key_field}': {exc}")
        raise

    return customer_map


def resolve_vendor_by_name(
    books_client: _CustomerSearchClient,
    vendor_name: str,
    *,
    aliases: Sequence[str] = (),
    active_only: bool = True,
    deduplicate: bool = True,
) -> dict[str, object] | None:
    """Resolve one Books vendor contact by exact case-insensitive name or alias."""
    target = require_text(vendor_name, "Vendor name")
    accepted = {target.casefold(), *(a.strip().casefold() for a in aliases if a.strip())}
    rows = require_records(
        books_client.contacts.list_all(
            params={"contact_type": "vendor", "search_text": target},
            resource_key="contacts",
        ),
        "Books vendor search",
    )
    matches = [
        row
        for row in rows
        if str(row.get("contact_name") or "").strip().casefold() in accepted
        and str(row.get("contact_type") or "").strip().casefold() == "vendor"
        and str(row.get("contact_id") or "").strip()
        and (
            not active_only
            or str(row.get("status") or "").strip().casefold() == "active"
        )
    ]
    if not deduplicate and len(matches) > 1:
        raise AmbiguousMatchError(f"Expected one vendor match for {target}, found {len(matches)}")
    return unique_record(matches, "contact_id")

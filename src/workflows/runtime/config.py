from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import TypedDict, TypeVar, overload

from utils.file_utils import json

try:
    import dotenvy_py

    def load_dotenv(dotenv_path: str | Path | None = None, **kwargs: object) -> bool:
        target = dotenv_path or ".env"
        if Path(target).exists():
            dotenvy_py.from_filename(str(target))
            return True
        return False
except ImportError:
    try:
        from dotenv import load_dotenv  # type: ignore[import-untyped]
    except ImportError:  # The base SDK can still use dependency-light workflows.
        def load_dotenv(*args: object, **kwargs: object) -> bool:
            return False

# 1. Project root & .env loading
root_dir = Path(__file__).resolve().parent.parent.parent.parent
env_path = root_dir / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()


class ProjectStructureConfig(TypedDict, total=False):
    max_nested_folder_depth: int
    max_files_per_directory: int


class DashboardWorkflowsConfig(TypedDict, total=False):
    include: list[str]
    exclude: list[str]


class RuntimeFileConfig(TypedDict, total=False):
    active_profile: str
    project_structure: ProjectStructureConfig
    profiles: dict[str, dict[str, object]]


def _flatten_profile(data: Mapping[str, object]) -> dict[str, object]:
    """Flatten section/workflow-grouped profile dictionaries for key lookup."""
    non_section_mappings = {
        "payment_creator_reports",
        "dashboard_workflows",
        "gstin_to_vendor_id",
        "gstin_aliases",
        "gstr1_financial_credit_notes",
        "neoseal_stock_count_worksheets",
        "neoseal_duplicate_map",
        "location_payment_prefixes",
        "selected_vendor_payment_moves",
    }
    result: dict[str, object] = {}
    for key, val in data.items():
        key_lower = key.lower()
        if isinstance(val, Mapping) and key_lower not in non_section_mappings:
            result[key_lower] = val
            result[key] = val
            for sub_key, sub_val in val.items():
                sub_key_lower = sub_key.lower()
                result[sub_key_lower] = sub_val
                result[sub_key] = sub_val
                prefix = f"{key_lower}_"
                if not sub_key_lower.startswith(prefix):
                    result[f"{prefix}{sub_key_lower}"] = sub_val
        else:
            result[key_lower] = val
            result[key] = val
    return result


def _load_config_dict(
    project_root: Path | None = None,
    home: Path | None = None,
) -> dict[str, object]:
    """Load the highest-priority YAML or legacy JSON configuration file.

    Project configuration intentionally takes precedence over user-level
    defaults. An existing but invalid file is an error: silently falling back
    could select identifiers for a different Zoho tenant.
    """
    project_root = project_root or root_dir
    home = home or Path.home()
    candidate_paths = [
        project_root / "config" / "config.yaml",
        project_root / "config" / "zoho_config.yaml",
        project_root / "config" / "zoho_config.json",
        project_root / "config" / "config.json",
        project_root / "zoho_config.json",
        project_root / "config.json",
        home / ".config" / "zoho" / "config.json",
        home / ".zoho" / "config.json",
    ]
    for path in candidate_paths:
        if path.exists() and path.is_file():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    if path.suffix == ".yaml":
                        try:
                            from utils.file_utils import yaml
                        except ImportError as exc:
                            raise ValueError(
                                f"Reading YAML configuration from {path} requires YAMLRocks; install the declared dependencies with uv."
                            ) from exc
                        try:
                            data = yaml.safe_load(f)
                        except yaml.YAMLError as exc:
                            raise ValueError(f"Unable to load Zoho configuration from {path}.") from exc
                    else:
                        data = json.load(f)
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"Unable to load Zoho configuration from {path}.") from exc
            if not isinstance(data, dict):
                raise ValueError(f"Zoho configuration in {path} must be a configuration object.")
            active_profile = data.get("active_profile")
            if active_profile:
                profiles = data.get("profiles")
                if not isinstance(profiles, dict):
                    raise ValueError(
                        f"Zoho configuration in {path} declares an active profile "
                        "without a profiles object."
                    )
                profile = profiles.get(active_profile)
                if not isinstance(profile, dict):
                    raise ValueError(
                        f"Active Zoho configuration profile {active_profile!r} "
                        f"was not found in {path}."
                    )
                return _flatten_profile(profile)
            return _flatten_profile(data)
    return {}


_FILE_CONFIG = _load_config_dict()

T = TypeVar("T")


@overload
def get_config(key: str, default: T) -> str | T: ...
@overload
def get_config(key: str) -> str: ...
def get_config(key: str, default: object = "") -> object:
    """Resolve config key: Environment variable -> file config -> default."""
    if key in os.environ:
        return os.environ[key]
    key_lower = key.lower()
    if key_lower in _FILE_CONFIG:
        return _FILE_CONFIG[key_lower]
    if key in _FILE_CONFIG:
        return _FILE_CONFIG[key]
    return default


def get_mapping_config(
    key: str,
    default: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Resolve a JSON object configuration value from files or the environment."""
    value = get_config(key, default or {})
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{key} must be a valid JSON object.") from exc
    if not isinstance(value, Mapping):
        raise ValueError(f"{key} must be a JSON object.")
    return dict(value)


def _parse_id_tuple(val: object) -> tuple[str, ...]:
    if isinstance(val, str):
        stripped = val.strip()
        if stripped.startswith("["):
            try:
                parsed = json.loads(stripped)
                if isinstance(parsed, Sequence):
                    return tuple(str(x).strip() for x in parsed if str(x).strip())
            except Exception:
                pass
        return tuple(part.strip() for part in val.split(",") if part.strip())
    if isinstance(val, Sequence):
        return tuple(str(x).strip() for x in val if str(x).strip())
    return ()


class Config:
    PROJECT_ROOT = str(root_dir)

    # API Access
    TOKEN_URL = str(get_config("TOKEN_URL", "http://localhost:3000/server/new/tokens"))
    ORG_ID = str(get_config("ORG_ID", ""))
    ANALYTICS_ORG_ID = str(get_config("ANALYTICS_ORG_ID", ""))
    ANALYTICS_WORKSPACE_ID = str(get_config(
        "ANALYTICS_WORKSPACE_ID", get_config("ZOHO_ANALYTICS_WORKSPACE_ID", "")
    ))
    ANALYTICS_DATE_MISMATCH_VIEW_ID = str(get_config("ANALYTICS_DATE_MISMATCH_VIEW_ID", ""))
    ANALYTICS_BANK_STATEMENT_VIEW_ID = str(get_config("ANALYTICS_BANK_STATEMENT_VIEW_ID", ""))
    ANALYTICS_CUSTOMER_FINDER_VIEW_ID = str(get_config("ANALYTICS_CUSTOMER_FINDER_VIEW_ID", ""))
    ANALYTICS_DETAILED_GL_VIEW_ID = str(get_config("ANALYTICS_DETAILED_GL_VIEW_ID", ""))
    ANALYTICS_UNDEPOSITED_CANDIDATES_VIEW_ID = str(get_config(
        "ANALYTICS_UNDEPOSITED_CANDIDATES_VIEW_ID", ""
    ))
    ANALYTICS_UNDEPOSITED_REPORT_VIEW_ID = str(get_config(
        "ANALYTICS_UNDEPOSITED_REPORT_VIEW_ID", ""
    ))
    INTER_LOCATION_CONTRA_VIEW_ID = str(get_config("INTER_LOCATION_CONTRA_VIEW_ID", ""))
    INTER_LOCATION_DIFF_VIEW_ID = str(get_config("INTER_LOCATION_DIFF_VIEW_ID", ""))
    DOMAIN = str(get_config("DOMAIN", "in"))
    CREATOR_OWNER_NAME = str(get_config(
        "CREATOR_OWNER_NAME", get_config("CREATOR_ACCOUNT_OWNER_NAME", "")
    ))
    PAYMENT_CREATOR_APP_LINK_NAME = str(get_config(
        "PAYMENT_CREATOR_APP_LINK_NAME", "order-management-new"
    ))
    PAYMENT_TRAVEL_EXPENSE_ACCOUNT_ID = str(get_config(
        "PAYMENT_TRAVEL_EXPENSE_ACCOUNT_ID", ""
    ))
    PAYMENT_SALARY_EXPENSE_ACCOUNT_ID = str(get_config("PAYMENT_SALARY_EXPENSE_ACCOUNT_ID", ""))
    PAYMENT_CASH_ACCOUNT_ID = str(get_config("PAYMENT_CASH_ACCOUNT_ID", ""))
    PAYMENT_CREATOR_REPORTS = {
        "online": "Online_Payments",
        "cheque": "Cheques",
        "cheque_detail": "All_Cheque_Details",
        "customer": "All_Customers1",
        "checkpoint": "All_Payments",
        **get_mapping_config("PAYMENT_CREATOR_REPORTS"),
    }
    DASHBOARD_WORKFLOWS = get_mapping_config(
        "DASHBOARD_WORKFLOWS",
        {"include": [], "exclude": []},
    )
    GSTR2_LOCATION_GSTIN_MAP = get_mapping_config("GSTR2_LOCATION_GSTIN_MAP")
    GSTIN_ALIASES = get_mapping_config("GSTIN_ALIASES")
    GSTR1_FINANCIAL_CREDIT_NOTES = get_mapping_config("GSTR1_FINANCIAL_CREDIT_NOTES")
    GSTR2_DEFAULT_JSON_PATH = str(get_config("GSTR2_DEFAULT_JSON_PATH", ""))
    GST_CASH_LEDGER_ACCOUNT_IDS = _parse_id_tuple(
        get_config("GST_CASH_LEDGER_ACCOUNT_IDS", ())
    )

    # Zoho WorkDrive Configurations
    POLYCAB_FOLDER_ID = str(get_config("POLYCAB_FOLDER_ID", ""))

    # Local Directory Paths
    FILES_DIR = str(get_config("FILES_DIR", str(root_dir / "input_files" / "polycab" / "cn")))
    POLYCAB_LEDGER_PATH = str(get_config(
        "POLYCAB_LEDGER_PATH", 
        str(root_dir / "input_files" / "polycab" / "ledger" / "277498_ReconciliationLedger_1-Jan-26_to_31-Mar-26.xls")
    ))

    # Zoho Books Entity IDs
    POLYCAB_VENDOR_ID = str(get_config("POLYCAB_VENDOR_ID", ""))
    POLYCAB_RMA_ITEM_ID = str(get_config("POLYCAB_RMA_ITEM_ID", ""))
    POLYCAB_RMA_ACCOUNT_ID = str(get_config("POLYCAB_RMA_ACCOUNT_ID", ""))
    POLYCAB_CLEARING_ACCOUNT_ID = str(get_config("POLYCAB_CLEARING_ACCOUNT_ID", ""))
    POLYCAB_SCHEME_ACCOUNT_ID = str(get_config("POLYCAB_SCHEME_ACCOUNT_ID", ""))
    NEOSEAL_PURCHASE_ACCOUNT_ID = str(get_config("NEOSEAL_PURCHASE_ACCOUNT_ID", ""))
    NEOSEAL_DUPLICATE_MAP = get_mapping_config("NEOSEAL_DUPLICATE_MAP", {})
    NEOSEAL_PRICE_LIST_GOOGLE_SHEET_ID = str(get_config(
        "NEOSEAL_PRICE_LIST_GOOGLE_SHEET_ID", ""
    ))
    GOOGLE_SHEETS_ACCESS_TOKEN = str(get_config("GOOGLE_SHEETS_ACCESS_TOKEN", ""))
    GOOGLE_APPLICATION_CREDENTIALS = str(get_config("GOOGLE_APPLICATION_CREDENTIALS", ""))
    NEOSEAL_STOCK_COUNT_SHEET_ID = str(get_config(
        "NEOSEAL_STOCK_COUNT_SHEET_ID", ""
    ))
    _neoseal_worksheets = get_mapping_config("NEOSEAL_STOCK_COUNT_WORKSHEETS", {})
    NEOSEAL_STOCK_COUNT_WORKSHEET = str(get_config(
        "NEOSEAL_STOCK_COUNT_WORKSHEET",
        _neoseal_worksheets.get("count", _neoseal_worksheets.get("worksheet", "StockCount")),
    ))
    NEOSEAL_STOCK_COUNT_FLAT_WORKSHEET = str(get_config(
        "NEOSEAL_STOCK_COUNT_FLAT_WORKSHEET",
        _neoseal_worksheets.get("flat", "Flat"),
    ))
    NEOSEAL_STOCK_COUNT_MAPPING_WORKSHEET = str(get_config(
        "NEOSEAL_STOCK_COUNT_MAPPING_WORKSHEET",
        _neoseal_worksheets.get("mapping", "Mapping"),
    ))
    FAN_PURCHASE_ACCOUNT_ID = str(get_config("FAN_PURCHASE_ACCOUNT_ID", ""))
    ZOHO_RSO_CN_ITEM_ID = str(get_config("ZOHO_RSO_CN_ITEM_ID", ""))
    ZOHO_SCHEME_CN_ITEM_ID = str(get_config("ZOHO_SCHEME_CN_ITEM_ID", ""))
    ZOHO_GST0_TAX_ID = str(get_config("ZOHO_GST0_TAX_ID", ""))
    ZOHO_TAX_SETTINGS_ID = str(get_config("ZOHO_TAX_SETTINGS_ID", ""))
    RSO_CUSTOMER_ID = str(get_config("RSO_CUSTOMER_ID", ""))
    SALES_ACCOUNT_ID = str(get_config("SALES_ACCOUNT_ID", ""))
    UNEARNED_REVENUE_ACCOUNT_ID = str(get_config("UNEARNED_REVENUE_ACCOUNT_ID", ""))
    INTER_BRANCH_ACCOUNT_ID = str(get_config("INTER_BRANCH_ACCOUNT_ID", ""))
    INTER_LOCATION_CLEARING_ACCOUNT_ID = str(get_config(
        "INTER_LOCATION_CLEARING_ACCOUNT_ID", ""
    ))
    LOCATION_PAYMENT_PREFIXES = get_mapping_config("LOCATION_PAYMENT_PREFIXES", {})
    INTER_LOCATION_EXCLUDED_PAYMENT_IDS = _parse_id_tuple(
        get_config("INTER_LOCATION_EXCLUDED_PAYMENT_IDS", ())
    )
    INTER_LOCATION_HANDLED_SPLIT_PAYMENT_IDS = _parse_id_tuple(
        get_config("INTER_LOCATION_HANDLED_SPLIT_PAYMENT_IDS", ())
    )
    SELECTED_VENDOR_PAYMENT_MOVES = get_mapping_config("SELECTED_VENDOR_PAYMENT_MOVES", {})

    # Zeiss
    ZEISS_VENDOR_ID = str(get_config("ZEISS_VENDOR_ID", ""))
    ZEISS_LEDGER_PATH = str(get_config(
        "ZEISS_LEDGER_PATH",
        str(root_dir / "input_files" / "zeiss" / "ZeissOct2025_Statement - ZeissOct2025_Statement.csv")
    ))

    # Location / Branch Config
    EXPECTED_LOCATION_ID = str(get_config("EXPECTED_LOCATION_ID", ""))
    EXPECTED_LOCATION_NAME = str(get_config("EXPECTED_LOCATION_NAME", ""))
    EXCLUDED_LOCATION_ID = str(get_config("EXCLUDED_LOCATION_ID", ""))

    # Bank Account IDs
    BANK_ACCOUNT_IDFC = str(get_config("BANK_ACCOUNT_IDFC", ""))
    BANK_ACCOUNT_HDFC = str(get_config("BANK_ACCOUNT_HDFC", ""))
    BANK_ACCOUNT_HDFC_AGENCIES = str(get_config("BANK_ACCOUNT_HDFC_AGENCIES", ""))
    BANK_ACCOUNT_ICICI = str(get_config("BANK_ACCOUNT_ICICI", ""))

    # GSTIN Map
    try:
        raw_gstin_map = get_config("GSTIN_TO_VENDOR_ID", "{}")
        if isinstance(raw_gstin_map, str):
            parsed_gstin = json.loads(raw_gstin_map)
            GSTIN_TO_VENDOR_ID: dict[str, str] = dict(parsed_gstin) if isinstance(parsed_gstin, Mapping) else {}
        elif isinstance(raw_gstin_map, Mapping):
            GSTIN_TO_VENDOR_ID = dict(raw_gstin_map)
        else:
            GSTIN_TO_VENDOR_ID = {}
    except Exception:
        GSTIN_TO_VENDOR_ID = {}

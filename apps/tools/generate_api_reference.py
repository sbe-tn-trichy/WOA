"""Generate Sphinx and Markdown API reference documentation from SDK code and comments."""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
from pathlib import Path
import re
import sys
from collections.abc import Sequence
from typing import Any

# Bootstrap workspace paths
_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class AttributeDoc:
    name: str
    annotation: str | None
    value: str | None
    comments: list[str] = field(default_factory=list)


@dataclass
class MethodDoc:
    name: str
    signature: str
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    comments: list[str] = field(default_factory=list)
    is_async: bool = False


@dataclass
class ClassDoc:
    name: str
    bases: list[str] = field(default_factory=list)
    docstring: str | None = None
    comments: list[str] = field(default_factory=list)
    attributes: list[AttributeDoc] = field(default_factory=list)
    methods: list[MethodDoc] = field(default_factory=list)


@dataclass
class FunctionDoc:
    name: str
    signature: str
    decorators: list[str] = field(default_factory=list)
    docstring: str | None = None
    comments: list[str] = field(default_factory=list)


@dataclass
class ModuleDoc:
    module_path: str
    rel_path: str
    docstring: str | None = None
    header_comments: list[str] = field(default_factory=list)
    classes: list[ClassDoc] = field(default_factory=list)
    functions: list[FunctionDoc] = field(default_factory=list)
    constants: list[AttributeDoc] = field(default_factory=list)
    all_exports: list[str] = field(default_factory=list)


KNOWN_MIXIN_METHODS: dict[str, list[tuple[str, str]]] = {
    "BaseResource": [
        ("list(params=None)", "Fetch one page of records from the resource endpoint."),
        ("list_iter(params=None, resource_key=None, per_page=200)", "Generator yielding records across pages without buffering all in memory."),
        ("list_all(params=None, resource_key=None, per_page=200)", "Auto-paginates and returns all records as a single list."),
        ("get(resource_id, params=None)", "Fetch a single record by resource identifier."),
        ("create(data, params=None, files=None)", "Create a record after validating required fields and defaults."),
        ("update(resource_id, data, params=None, files=None)", "Update an existing record."),
        ("delete(resource_id, params=None)", "Delete an existing record."),
        ("_action(method, resource_id, action, ...)", "Execute a sub-action endpoint (e.g. status changes, sub-resources)."),
    ],
    "StatusMixin": [
        ("mark_as_open(resource_id)", "Transition resource status to 'open'."),
        ("mark_as_sent(resource_id)", "Transition resource status to 'sent'."),
        ("mark_as_draft(resource_id)", "Transition resource status to 'draft'."),
        ("mark_as_void(resource_id)", "Transition resource status to 'void'."),
    ],
    "ActiveInactiveMixin": [
        ("mark_as_active(resource_id)", "Mark resource as active."),
        ("mark_as_inactive(resource_id)", "Mark resource as inactive."),
    ],
    "ApprovalMixin": [
        ("submit_for_approval(resource_id)", "Submit resource for multi-level approval."),
        ("approve(resource_id)", "Approve submitted resource."),
    ],
    "EmailMixin": [
        ("email(resource_id, data, params=None)", "Send resource statement or notification via email."),
    ],
    "CreditsMixin": [
        ("apply_credits(resource_id, data)", "Apply customer or vendor credits against the document."),
    ],
}


def _format_arg(arg: ast.arg, default: ast.expr | None = None) -> str:
    parts = [arg.arg]
    if arg.annotation:
        parts.append(f": {ast.unparse(arg.annotation)}")
    if default is not None:
        parts.append(f" = {ast.unparse(default)}")
    return "".join(parts)


def format_func_signature(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    args_list: list[str] = []

    posonly = func_node.args.posonlyargs
    pos_args = func_node.args.args
    defaults = func_node.args.defaults

    all_pos = posonly + pos_args
    num_defaults = len(defaults)
    first_default_idx = len(all_pos) - num_defaults

    for i, a in enumerate(posonly):
        d = defaults[i - first_default_idx] if i >= first_default_idx else None
        args_list.append(_format_arg(a, d))
    if posonly:
        args_list.append("/")

    for i, a in enumerate(pos_args, start=len(posonly)):
        d = defaults[i - first_default_idx] if i >= first_default_idx else None
        args_list.append(_format_arg(a, d))

    if func_node.args.vararg:
        va = "*" + func_node.args.vararg.arg
        if func_node.args.vararg.annotation:
            va += f": {ast.unparse(func_node.args.vararg.annotation)}"
        args_list.append(va)
    elif func_node.args.kwonlyargs:
        args_list.append("*")

    for a, d in zip(func_node.args.kwonlyargs, func_node.args.kw_defaults):
        args_list.append(_format_arg(a, d))

    if func_node.args.kwarg:
        ka = "**" + func_node.args.kwarg.arg
        if func_node.args.kwarg.annotation:
            ka += f": {ast.unparse(func_node.args.kwarg.annotation)}"
        args_list.append(ka)

    ret = f" -> {ast.unparse(func_node.returns)}" if func_node.returns else ""
    prefix = "async def " if isinstance(func_node, ast.AsyncFunctionDef) else "def "
    return f"{prefix}{func_node.name}({', '.join(args_list)}){ret}"


def get_leading_comments(source_lines: Sequence[str], lineno: int) -> list[str]:
    comments: list[str] = []
    idx = lineno - 2
    while idx >= 0:
        line = source_lines[idx].strip()
        if line.startswith("#"):
            comments.append(line.lstrip("#").strip())
            idx -= 1
        else:
            break
    comments.reverse()
    return comments


def get_header_comments(source_lines: Sequence[str]) -> list[str]:
    comments: list[str] = []
    for line in source_lines:
        line_s = line.strip()
        if not line_s:
            continue
        if line_s.startswith("#"):
            if not line_s.startswith("#!") and "coding:" not in line_s:
                comments.append(line_s.lstrip("#").strip())
        else:
            break
    return comments


def get_trailing_comment(line: str) -> str | None:
    if "#" in line:
        parts = line.split("#", 1)
        comment = parts[1].strip()
        if comment:
            return comment
    return None


def parse_module(filepath: Path) -> ModuleDoc:
    content = filepath.read_text(encoding="utf-8")
    source_lines = content.splitlines()
    tree = ast.parse(content, filename=str(filepath))

    rel_path = filepath.as_posix()
    if "src/" in rel_path:
        mod_name = rel_path.split("src/", 1)[1].replace("/", ".").removesuffix(".py").removesuffix(".__init__")
    else:
        mod_name = filepath.stem

    docstring = ast.get_docstring(tree)
    header_comments = get_header_comments(source_lines)

    classes: list[ClassDoc] = []
    functions: list[FunctionDoc] = []
    constants: list[AttributeDoc] = []
    all_exports: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            c_doc = ast.get_docstring(node)
            c_comments = get_leading_comments(source_lines, node.lineno)
            bases = [ast.unparse(b) for b in node.bases]
            c_attrs: list[AttributeDoc] = []
            c_methods: list[MethodDoc] = []

            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    # Skip private dunders, except __init__
                    if item.name.startswith("__") and item.name != "__init__":
                        continue
                    # Skip private methods starting with _ unless they have a docstring or are known hooks
                    if item.name.startswith("_") and not item.name.startswith("__") and item.name not in {
                        "_action", "_request", "_prepare_payload", "_raise_for_status",
                    } and not ast.get_docstring(item):
                        continue

                    m_doc = ast.get_docstring(item)
                    m_comments = get_leading_comments(source_lines, item.lineno)
                    decs = [f"@{ast.unparse(d)}" for d in item.decorator_list]
                    sig = format_func_signature(item)
                    c_methods.append(
                        MethodDoc(
                            name=item.name,
                            signature=sig,
                            decorators=decs,
                            docstring=m_doc,
                            comments=m_comments,
                            is_async=isinstance(item, ast.AsyncFunctionDef),
                        )
                    )
                elif isinstance(item, ast.Assign):
                    for target in item.targets:
                        t_name = ast.unparse(target)
                        if not t_name.startswith("_"):
                            val = ast.unparse(item.value)
                            comments = get_leading_comments(source_lines, item.lineno)
                            if item.lineno - 1 < len(source_lines):
                                trailing = get_trailing_comment(source_lines[item.lineno - 1])
                                if trailing and trailing not in comments:
                                    comments.append(trailing)
                            c_attrs.append(AttributeDoc(name=t_name, annotation=None, value=val, comments=comments))
                elif isinstance(item, ast.AnnAssign):
                    t_name = ast.unparse(item.target)
                    if not t_name.startswith("_"):
                        ann = ast.unparse(item.annotation)
                        val = ast.unparse(item.value) if item.value else None
                        comments = get_leading_comments(source_lines, item.lineno)
                        if item.lineno - 1 < len(source_lines):
                            trailing = get_trailing_comment(source_lines[item.lineno - 1])
                            if trailing and trailing not in comments:
                                comments.append(trailing)
                        c_attrs.append(AttributeDoc(name=t_name, annotation=ann, value=val, comments=comments))

            classes.append(ClassDoc(name=node.name, bases=bases, docstring=c_doc, comments=c_comments, attributes=c_attrs, methods=c_methods))

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not node.name.startswith("_"):
                f_doc = ast.get_docstring(node)
                f_comments = get_leading_comments(source_lines, node.lineno)
                decs = [f"@{ast.unparse(d)}" for d in node.decorator_list]
                sig = format_func_signature(node)
                functions.append(FunctionDoc(name=node.name, signature=sig, decorators=decs, docstring=f_doc, comments=f_comments))

        elif isinstance(node, ast.Assign):
            for target in node.targets:
                t_name = ast.unparse(target)
                if t_name == "__all__" and isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                    for elt in node.value.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            all_exports.append(elt.value)
                elif not t_name.startswith("_") and t_name.isupper():
                    val = ast.unparse(node.value)
                    comments = get_leading_comments(source_lines, node.lineno)
                    constants.append(AttributeDoc(name=t_name, annotation=None, value=val, comments=comments))
        elif isinstance(node, ast.AnnAssign):
            t_name = ast.unparse(node.target)
            if not t_name.startswith("_") and t_name.isupper():
                ann = ast.unparse(node.annotation)
                val = ast.unparse(node.value) if node.value else None
                comments = get_leading_comments(source_lines, node.lineno)
                constants.append(AttributeDoc(name=t_name, annotation=ann, value=val, comments=comments))

    return ModuleDoc(
        module_path=mod_name,
        rel_path=filepath.relative_to(ROOT).as_posix() if filepath.is_relative_to(ROOT) else filepath.as_posix(),
        docstring=docstring,
        header_comments=header_comments,
        classes=classes,
        functions=functions,
        constants=constants,
        all_exports=all_exports,
    )


def clean_docstring(doc: str | None) -> str:
    if not doc:
        return ""
    lines = doc.strip().splitlines()
    cleaned = []
    for line in lines:
        cleaned.append(line)
    return "\n".join(cleaned).strip()


def render_markdown_section(
    title: str,
    description: str,
    modules: Sequence[ModuleDoc],
    custom_intro: str = "",
    custom_appendix: str = "",
) -> str:
    lines: list[str] = [
        "<!-- Auto-generated by apps/generate_api_reference.py. Do not edit directly. -->",
        f"# {title}",
        "",
        description.strip(),
        "",
    ]

    if custom_intro:
        lines.append(custom_intro.strip())
        lines.append("")

    # Table of contents for the page
    lines.append("## Table of Contents")
    lines.append("")
    for mod in modules:
        anchor = mod.module_path.replace(".", "-").lower()
        lines.append(f"- [`{mod.module_path}`](#{anchor})")
        for cls in mod.classes:
            cls_anchor = f"{anchor}-{cls.name.lower()}"
            lines.append(f"  - [Class `{cls.name}`](#{cls_anchor})")
        for fn in mod.functions:
            fn_anchor = f"{anchor}-{fn.name.lower()}"
            lines.append(f"  - [Function `{fn.name}`](#{fn_anchor})")
    lines.append("")
    lines.append("---")
    lines.append("")

    for mod in modules:
        mod_anchor = mod.module_path.replace(".", "-").lower()
        lines.append(f"## Module `{mod.module_path}`")
        lines.append("")
        lines.append(f"**Source:** [`{mod.rel_path}`]({mod.rel_path})")
        lines.append("")

        if mod.docstring:
            lines.append(clean_docstring(mod.docstring))
            lines.append("")
        elif mod.header_comments:
            lines.append("> " + "\n> ".join(mod.header_comments))
            lines.append("")

        if mod.all_exports:
            lines.append("**Declared Exports (`__all__`):**")
            lines.append(", ".join(f"`{exp}`" for exp in mod.all_exports))
            lines.append("")

        if mod.constants:
            lines.append("### Constants & Settings")
            lines.append("")
            lines.append("| Constant | Type | Value | Description |")
            lines.append("|---|---|---|---|")
            for c in mod.constants:
                ann = f"`{c.annotation}`" if c.annotation else "-"
                val_short = (c.value or "").replace("|", "\\|")
                if len(val_short) > 40:
                    val_short = val_short[:37] + "..."
                val_fmt = f"`{val_short}`" if val_short else "-"
                desc = " ".join(c.comments) if c.comments else "-"
                lines.append(f"| `{c.name}` | {ann} | {val_fmt} | {desc} |")
            lines.append("")

        for cls in mod.classes:
            cls_anchor = f"{mod_anchor}-{cls.name.lower()}"
            lines.append(f"### Class `{cls.name}`")
            lines.append("")
            if cls.bases:
                lines.append(f"**Bases:** {', '.join(f'`{b}`' for b in cls.bases)}")
                lines.append("")

            if cls.docstring:
                lines.append(clean_docstring(cls.docstring))
                lines.append("")
            elif cls.comments:
                lines.append("> " + "\n> ".join(cls.comments))
                lines.append("")

            # Class attributes
            if cls.attributes:
                lines.append("#### Class Attributes")
                lines.append("")
                lines.append("| Attribute | Type | Default Value | Notes |")
                lines.append("|---|---|---|---|")
                for attr in cls.attributes:
                    ann = f"`{attr.annotation}`" if attr.annotation else "-"
                    val_short = (attr.value or "").replace("|", "\\|")
                    if len(val_short) > 45:
                        val_short = val_short[:42] + "..."
                    val_fmt = f"`{val_short}`" if val_short else "-"
                    notes = " ".join(attr.comments) if attr.comments else "-"
                    lines.append(f"| `{attr.name}` | {ann} | {val_fmt} | {notes} |")
                lines.append("")

            # Mixin inherited capabilities
            inherited_mixins = [b for b in cls.bases if b in KNOWN_MIXIN_METHODS]
            if inherited_mixins:
                lines.append("#### Inherited Mixin Capabilities")
                lines.append("")
                for mixin_name in inherited_mixins:
                    lines.append(f"**From `{mixin_name}`:**")
                    lines.append("")
                    for sig, desc in KNOWN_MIXIN_METHODS[mixin_name]:
                        lines.append(f"- `{sig}`: {desc}")
                    lines.append("")

            # Methods
            if cls.methods:
                lines.append("#### Methods")
                lines.append("")
                for m in cls.methods:
                    lines.append(f"##### `{cls.name}.{m.name}`")
                    lines.append("")
                    if m.decorators:
                        lines.append("```python")
                        for d in m.decorators:
                            lines.append(d)
                        lines.append(m.signature)
                        lines.append("```")
                    else:
                        lines.append(f"```python\n{m.signature}\n```")
                    lines.append("")

                    if m.docstring:
                        lines.append(clean_docstring(m.docstring))
                        lines.append("")
                    elif m.comments:
                        lines.append("> " + "\n> ".join(m.comments))
                        lines.append("")

        for fn in mod.functions:
            lines.append(f"### Function `{fn.name}`")
            lines.append("")
            if fn.decorators:
                lines.append("```python")
                for d in fn.decorators:
                    lines.append(d)
                lines.append(fn.signature)
                lines.append("```")
            else:
                lines.append(f"```python\n{fn.signature}\n```")
            lines.append("")

            if fn.docstring:
                lines.append(clean_docstring(fn.docstring))
                lines.append("")
            elif fn.comments:
                lines.append("> " + "\n> ".join(fn.comments))
                lines.append("")

        lines.append("---")
        lines.append("")

    if custom_appendix:
        lines.append(custom_appendix.strip())
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def render_erp_summary(erp_generated_file: Path) -> str:
    """Read the typed registry and resource ASTs without importing SDK modules."""
    from utils.file_utils import json

    package = erp_generated_file.parent
    tree = ast.parse((package / "registry.py").read_text(encoding="utf-8"))
    sources = {
        entry.name: package / (node.module.replace(".", "/") + ".py")
        for node in tree.body if isinstance(node, ast.ImportFrom) and node.module
        for entry in node.names
    }
    attributes = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "ERPResources")
    raw_manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    manifest: dict[str, Any] = raw_manifest if isinstance(raw_manifest, dict) else {}
    resources = []
    for field in attributes.body:
        if not isinstance(field, ast.AnnAssign):
            continue
        if not isinstance(field.target, ast.Name) or not isinstance(field.annotation, ast.Name):
            continue
        attribute, cls = field.target.id, field.annotation.id
        path = sources[cls]
        definition = next(node for node in ast.parse(path.read_text(encoding="utf-8")).body
                          if isinstance(node, ast.ClassDef) and node.name == cls)
        methods = [node.name for node in definition.body if isinstance(node, ast.FunctionDef)]
        if methods != [operation["name"] for operation in manifest[attribute]["operations"]]:
            raise ValueError(f"ERP documentation disagrees with manifest for {attribute}")
        doc = ast.get_docstring(definition) or "ERP resource operations"
        resources.append((cls, attribute, doc.splitlines()[0], len(methods), methods[:4], path))
    if [entry[1] for entry in resources] != list(manifest):
        raise ValueError("ERP documentation registry coverage/order disagrees with manifest")
    total = sum(entry[3] for entry in resources)

    lines = [
        f"## Generated ERP Resource Catalog ({len(resources)} Resources, {total} Operations)",
        "",
        f"The Zoho ERP SDK includes {len(resources)} typed resources generated from OpenAPI specifications.",
        "Each resource is available as an attribute on `ZohoERPAPI` (e.g. `client.addons`, `client.invoices`).",
        "",
        "| Resource Class | Attribute Name | Total Operations | Sample Operations | Description | Source |",
        "|---|---|---|---|---|---|",
    ]

    for name, attr_name, desc, count, samples, path in resources:
        samples_str = ", ".join(f"`{s}`" for s in samples)
        if count > len(samples):
            samples_str += f" (+{count - len(samples)} more)"
        source = path.relative_to(ROOT).as_posix()
        lines.append(f"| `{name}` | `client.{attr_name}` | {count} | {samples_str} | {desc} | [source](../../{source}) |")

    lines.append("")
    lines.append("See [`okf/zoho-erp.md`](../../okf/zoho-erp.md) for full endpoint routing, YAML generation, and token management.")
    lines.append("")
    return "\n".join(lines)


def render_analytics_summary(package: Path) -> str:
    """Build the Analytics domain index from the generated operation manifest."""
    from utils.file_utils import json

    raw_manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    manifest: dict[str, Any] = raw_manifest if isinstance(raw_manifest, dict) else {}
    total = sum(len(domain["operations"]) for domain in manifest.values())
    lines = [
        f"## Generated Analytics API ({len(manifest)} Domains, {total} Operations)",
        "",
        "| Client resource | Operations | Source |",
        "|---|---:|---|",
    ]
    for name, domain in manifest.items():
        path = (package / domain["module"]).relative_to(ROOT).as_posix()
        lines.append(f"| `client.openapi.{name}` | {len(domain['operations'])} | [source](../../{path}) |")
    manifest_path = (package / "manifest.json").relative_to(ROOT).as_posix()
    lines.extend([
        "",
        f"See the [operation manifest](../../{manifest_path}) for routes and OAuth scopes.",
        "See the [Analytics SDK reference](../../okf/zoho-analytics.md) for request and generation details.",
        "",
    ])
    return "\n".join(lines)


@dataclass
class SectionSpec:
    filename: str
    title: str
    description: str
    file_patterns: list[str]
    custom_intro: str = ""
    is_erp: bool = False


SECTIONS: list[SectionSpec] = [
    SectionSpec(
        filename="core.md",
        title="Core SDK & Transport Architecture",
        description="Shared HTTP transport, authentication managers, base resource abstractions, exception hierarchies, security path sanitizers, validators, custom identifiers, and file download utilities.",
        file_patterns=[
            "src/utils/http_utils/http.py",
            "src/utils/file_utils/json.py",
            "src/utils/http_utils/http_transport.py",
            "src/utils/file_utils/yaml.py",
            "src/utils/file_utils/pdf.py",
            "src/utils/general_utils/sequences.py",
            "src/utils/general_utils/module_aliases.py",
            "src/utils/general_utils/encoding.py",
            "src/zoho/core_sdk/auth.py",
            "src/zoho/core_sdk/base_client.py",
            "src/zoho/core_sdk/base_resource.py",
            "src/zoho/core_sdk/exceptions.py",
            "src/zoho/core_sdk/security.py",
            "src/zoho/core_sdk/validation.py",
            "src/zoho/core_sdk/identifiers.py",
            "src/zoho/core_sdk/logging.py",
        ],
    ),
    SectionSpec(
        filename="books.md",
        title="Zoho Books API Reference",
        description="Complete reference for the Zoho Books client, CRUD resources, status and approval mixins, contacts, banking, sales, purchases, GST outward reporting, time tracking, custom fields, and financial statements.",
        file_patterns=[
            "src/zoho/books/client.py",
            "src/zoho/books/base.py",
            "src/zoho/books/custom/mixins.py",
            "src/zoho/books/custom/contacts.py",
            "src/zoho/books/custom/sales.py",
            "src/zoho/books/custom/purchases.py",
            "src/zoho/books/custom/banking.py",
            "src/zoho/books/custom/gst.py",
            "src/zoho/books/custom/projects.py",
            "src/zoho/books/custom/reports.py",
            "src/zoho/books/custom/ledger.py",
        ],
    ),
    SectionSpec(
        filename="inventory.md",
        title="Zoho Inventory API Reference",
        description="Complete reference for the Zoho Inventory client, item catalogs, item groups, inventory adjustments, move orders, transfer orders, packages, shipments, picklists, bins, and batches.",
        file_patterns=[
            "src/zoho/inventory/client.py",
            "src/zoho/inventory/base.py",
            "src/zoho/inventory/resources/catalog/items.py",
            "src/zoho/inventory/resources/catalog/item_groups.py",
            "src/zoho/inventory/resources/movements/inventory_adjustments.py",
            "src/zoho/inventory/resources/movements/move_orders.py",
            "src/zoho/inventory/resources/movements/transfer_orders.py",
            "src/zoho/inventory/resources/fulfillment/packages.py",
            "src/zoho/inventory/resources/fulfillment/shipments.py",
            "src/zoho/inventory/resources/fulfillment/picklists.py",
            "src/zoho/inventory/resources/catalog/bins.py",
            "src/zoho/inventory/resources/catalog/batches.py",
        ],
    ),
    SectionSpec(
        filename="analytics.md",
        title="Zoho Analytics API Reference",
        description="Zoho Analytics v2 OpenAPI resources, dynamic SQL queries, view exports, and resumable metadata snapshots.",
        file_patterns=[
            "src/zoho/analytics/client.py",
            "src/zoho/analytics/custom/resources.py",
            "src/zoho/analytics/custom/metadata.py",
            "src/zoho/analytics/custom/snapshot.py",
            "src/zoho/analytics/exceptions.py",
        ],
    ),
    SectionSpec(
        filename="erp.md",
        title="Zoho ERP API Reference",
        description="Typed Zoho ERP client sharing the SDK OAuth transport with 81 generated OpenAPI resources and 899 operations across ERP v1 and v3 endpoints.",
        file_patterns=[
            "src/zoho/erp/client.py",
            "src/zoho/erp/openapi/resource.py",
        ],
        is_erp=True,
    ),
    SectionSpec(
        filename="creator.md",
        title="Zoho Creator API Reference",
        description="Zoho Creator client for low-code application forms, reports, attachment streaming, and bulk record operations.",
        file_patterns=[
            "src/zoho/creator/client.py",
            "src/zoho/creator/exceptions.py",
        ],
    ),
    SectionSpec(
        filename="mail.md",
        title="Zoho Mail API Reference",
        description="Zoho Mail client for managing email accounts, folders, and sending/listing email messages with attachments.",
        file_patterns=[
            "src/zoho/mail/client.py",
            "src/zoho/mail/base.py",
            "src/zoho/mail/resources/accounts.py",
            "src/zoho/mail/resources/folders.py",
            "src/zoho/mail/resources/messages.py",
            "src/zoho/mail/exceptions.py",
        ],
    ),
    SectionSpec(
        filename="wd.md",
        title="Zoho WorkDrive API Reference",
        description="Zoho WorkDrive client for file and folder management, streaming uploads, recursive folder downloads, and duplicate folder cleanup.",
        file_patterns=[
            "src/zoho/wd/client.py",
            "src/zoho/wd/base.py",
            "src/zoho/wd/resources/files.py",
            "src/zoho/wd/exceptions.py",
        ],
    ),
    SectionSpec(
        filename="sheet.md",
        title="Zoho Sheet API Reference",
        description="Zoho Sheet client for workbook, worksheet, and tabular row manipulation.",
        file_patterns=[
            "src/zoho/sheet/client.py",
        ],
    ),
    SectionSpec(
        filename="cliq.md",
        title="Zoho Cliq API Reference",
        description="Zoho Cliq client for broadcasting channel notifications and bot messages.",
        file_patterns=[
            "src/zoho/cliq/client.py",
        ],
    ),
    SectionSpec(
        filename="helpers.md",
        title="SDK Shared Helper Utilities Reference",
        description="Reusable financial helpers: fiscal-year date parsing, sequence numbering, account transactions, GST validation, item filtering, ledger balances, and record normalization.",
        file_patterns=[
            "src/helpers/formatting/dates.py",
            "src/helpers/reports/accounts.py",
            "src/helpers/catalog/bins.py",
            "src/helpers/catalog/contacts.py",
            "src/helpers/catalog/custom_fields.py",
            "src/helpers/reports/equity_ledger.py",
            "src/helpers/operations/files.py",
            "src/helpers/formatting/gst.py",
            "src/helpers/reports/inter_branch_ledger.py",
            "src/helpers/catalog/items.py",
            "src/helpers/reports/profit_and_loss.py",
            "src/helpers/operations/records.py",
            "src/helpers/formatting/references.py",
            "src/helpers/operations/transactions.py",
        ],
    ),
    SectionSpec(
        filename="google_sheets.md",
        title="Google Sheets API v4 SDK Reference",
        description="Google Sheets API v4 client supporting both OAuth token and Service Account credentials with range reading, updating, and formatting.",
        file_patterns=[
            "src/google_sheets/client.py",
            "src/google_sheets/auth.py",
            "src/google_sheets/exceptions.py",
        ],
    ),
]


def render_api_index(sections: Sequence[SectionSpec], all_modules: dict[str, list[ModuleDoc]]) -> str:
    lines = [
        "<!-- Auto-generated by apps/generate_api_reference.py. Do not edit directly. -->",
        "# WOA — Generated API Reference",
        "",
        "> **Notice:** This API reference is automatically generated directly from the codebase AST,",
        "> signatures, type annotations, docstrings, and inline module comments.",
        "> To regenerate, run `.venv/bin/python apps/generate_api_reference.py`.",
        "",
        "## Overview",
        "",
        "The `WOA` provides typed, robust Python clients for Zoho enterprise services,",
        "built-in OAuth2 token caching, Catalyst token switching, rate-limiting handlers,",
        "and security sanitizers.",
        "",
        "## Documentation Sections",
        "",
        "| Section | Target File | Description | Primary Classes / Symbols |",
        "|---|---|---|---|",
    ]

    for sec in sections:
        mods = all_modules.get(sec.filename, [])
        primary_classes: list[str] = []
        for m in mods:
            for c in m.classes:
                if not c.name.startswith("_"):
                    primary_classes.append(f"`{c.name}`")
        for m in mods:
            for f in m.functions:
                if not f.name.startswith("_"):
                    primary_classes.append(f"`{f.name}()`")

        classes_summary = ", ".join(primary_classes[:4])
        if len(primary_classes) > 4:
            classes_summary += f" (+{len(primary_classes) - 4} more)"
        if sec.is_erp:
            classes_summary = "`ZohoERPAPI`, `ERPResource`, 81 generated resources"

        lines.append(f"| **{sec.title}** | [{sec.filename}]({sec.filename}) | {sec.description} | {classes_summary} |")

    lines.append("")
    lines.append("## Quick Start")
    lines.append("")
    lines.append("### Connecting to Zoho Books")
    lines.append("```python")
    lines.append("from zoho import ZohoBooksAPI, ZohoOAuth2Manager")
    lines.append("")
    lines.append("oauth = ZohoOAuth2Manager(")
    lines.append("    client_id='your_client_id',")
    lines.append("    client_secret='your_client_secret',")
    lines.append("    refresh_token='your_refresh_token',")
    lines.append("    domain='in'")
    lines.append(")")
    lines.append("")
    lines.append("books = ZohoBooksAPI(")
    lines.append("    access_token=oauth.get_access_token(),")
    lines.append("    organization_id='123456789',")
    lines.append("    domain='in',")
    lines.append("    token_refresh_callback=oauth.get_access_token")
    lines.append(")")
    lines.append("")
    lines.append("# Auto-paginated bill iterator")
    lines.append("for bill in books.bills.list_iter(resource_key='bills'):")
    lines.append("    print(bill['bill_number'], bill['total'])")
    lines.append("```")
    lines.append("")
    lines.append("### Connecting to Zoho Inventory")
    lines.append("```python")
    lines.append("from zoho import ZohoInventoryAPI")
    lines.append("")
    lines.append("inventory = ZohoInventoryAPI(")
    lines.append("    access_token='your_access_token',")
    lines.append("    organization_id='123456789',")
    lines.append("    domain='in'")
    lines.append(")")
    lines.append("")
    lines.append("for item in inventory.items.list_iter(resource_key='items'):")
    lines.append("    print(item['name'], item.get('actual_available_stock'))")
    lines.append("```")
    lines.append("")
    lines.append("### Public API Exports")
    lines.append("")
    lines.append("All primary client classes and exceptions can be imported directly from the top-level package:")
    lines.append("```python")
    lines.append("from zoho import (")
    lines.append("    ZohoBooksAPI, ZohoBooksError,")
    lines.append("    ZohoInventoryAPI, ZohoInventoryError,")
    lines.append("    ZohoAnalyticsAPI, ZohoAnalyticsError,")
    lines.append("    ZohoERPAPI, ZohoERPError,")
    lines.append("    ZohoCreatorAPI, ZohoCreatorError,")
    lines.append("    ZohoMailAPI, ZohoMailError,")
    lines.append("    ZohoWorkdriveAPI,")
    lines.append("    ZohoSheetAPI,")
    lines.append("    ZohoCliqAPI,")
    lines.append("    ZohoOAuth2Manager, CatalystAuth, HttpTokenProvider,")
    lines.append("    ZohoError, ZohoAuthError,")
    lines.append("    sanitize_filename, resolve_output_path,")
    lines.append(")")
    lines.append("```")
    lines.append("")
    lines.append("---")
    lines.append("See [`INDEX.md`](../../INDEX.md) for navigation reference and `AGENTS.md` for architecture policy.")
    lines.append("")
    return "\n".join(lines)


def render_sphinx_conf() -> str:
    return '''"""Sphinx configuration for WOA documentation."""
import os
import sys

# Add src to sys.path
sys.path.insert(0, os.path.abspath("../src"))

project = "WOA"
copyright = "2026, WOA Contributors"
author = "WOA Contributors"
release = "0.2.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.viewcode",
    "sphinx.ext.napoleon",
]

# Support Markdown parser if available
try:
    import myst_parser  # noqa: F401
    extensions.append("myst_parser")
    source_suffix = {
        ".rst": "restructuredtext",
        ".md": "markdown",
    }
except ImportError:
    source_suffix = [".rst", ".md"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "alabaster"
html_static_path = ["_static"]
'''


def render_sphinx_index_rst() -> str:
    return """.. WOA documentation master file.

WOA Documentation
======================

Typed Python SDK for Zoho API services with shared transport, OAuth2 management,
and multi-service domain workflows.

.. toctree::
   :maxdepth: 2
   :caption: API Reference

   api/README
   api/core
   api/books
   api/inventory
   api/analytics
   api/erp
   api/creator
   api/mail
   api/wd
   api/sheet
   api/cliq
   api/helpers
   api/google_sheets
"""


def render_root_index_md() -> str:
    return """# WOA Documentation

Welcome to the WOA API reference documentation.

- [API Reference Overview](api/README.md)
- [Core SDK & Transport Architecture](api/core.md)
- [Zoho Books API](api/books.md)
- [Zoho Inventory API](api/inventory.md)
- [Zoho Analytics API](api/analytics.md)
- [Zoho ERP API](api/erp.md)
- [Zoho Creator API](api/creator.md)
- [Zoho Mail API](api/mail.md)
- [Zoho WorkDrive API](api/wd.md)
- [Zoho Sheet API](api/sheet.md)
- [Zoho Cliq API](api/cliq.md)
- [SDK Helper Utilities](api/helpers.md)
- [Google Sheets API v4 SDK](api/google_sheets.md)
"""


def generate_all_docs(
    docs_root: Path,
    output_dir: Path,
    check_only: bool = False,
    verbose: bool = False,
) -> tuple[bool, list[str]]:
    """Generate all API reference documents and Sphinx configuration.
    
    Returns (is_in_sync, list_of_changed_or_missing_files).
    """
    plan: dict[Path, str] = {}

    all_modules_by_sec: dict[str, list[ModuleDoc]] = {}

    for sec in SECTIONS:
        modules: list[ModuleDoc] = []
        for pattern in sec.file_patterns:
            p = ROOT / pattern
            if p.exists():
                modules.append(parse_module(p))
            else:
                if verbose:
                    print(f"Warning: pattern path not found: {p}")

        all_modules_by_sec[sec.filename] = modules

        custom_appendix = ""
        if sec.is_erp:
            erp_gen_file = ROOT / "src/zoho/erp/openapi/generated.py"
            if erp_gen_file.exists():
                custom_appendix = render_erp_summary(erp_gen_file)
        elif sec.filename == "analytics.md":
            custom_appendix = render_analytics_summary(ROOT / "src/zoho/analytics/openapi")

        content = render_markdown_section(
            title=sec.title,
            description=sec.description,
            modules=modules,
            custom_intro=sec.custom_intro,
            custom_appendix=custom_appendix,
        )
        plan[output_dir / sec.filename] = content

    # Render central API index
    plan[output_dir / "README.md"] = render_api_index(SECTIONS, all_modules_by_sec)

    # Render Sphinx configuration and root index
    plan[docs_root / "conf.py"] = render_sphinx_conf()
    plan[docs_root / "index.rst"] = render_sphinx_index_rst()
    plan[docs_root / "index.md"] = render_root_index_md()

    changed_files: list[str] = []

    for file_path, expected_content in plan.items():
        if file_path.exists():
            existing = file_path.read_text(encoding="utf-8")
            if existing != expected_content:
                changed_files.append(file_path.as_posix())
                if not check_only:
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    file_path.write_text(expected_content, encoding="utf-8")
                    if verbose:
                        print(f"Updated: {file_path}")
        else:
            changed_files.append(file_path.as_posix())
            if not check_only:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(expected_content, encoding="utf-8")
                if verbose:
                    print(f"Created: {file_path}")

    is_in_sync = len(changed_files) == 0
    return is_in_sync, changed_files


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Sphinx and Markdown API reference from SDK code.")
    parser.add_argument("--docs-root", type=Path, default=ROOT / "docs", help="Docs root directory")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs" / "api", help="API reference output directory")
    parser.add_argument("--check", action="store_true", help="Verify if docs are in sync without writing")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose progress messages")
    args = parser.parse_args()

    docs_root = args.docs_root.resolve()
    output_dir = args.output_dir.resolve()

    if args.verbose:
        print(f"Docs root: {docs_root}")
        print(f"Output directory: {output_dir}")

    in_sync, changed = generate_all_docs(docs_root, output_dir, check_only=args.check, verbose=args.verbose)

    if args.check:
        if in_sync:
            print("Documentation is up to date.")
            return 0
        else:
            print(f"Documentation out of sync. {len(changed)} file(s) differ or missing:")
            for c in changed:
                print(f"  - {c}")
            return 1
    else:
        print(f"Successfully generated API reference in {output_dir} ({len(changed)} file(s) written).")
        return 0


if __name__ == "__main__":
    sys.exit(main())

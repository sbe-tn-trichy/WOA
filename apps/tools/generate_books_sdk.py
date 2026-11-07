"""Generate additive Books API wrappers from local OpenAPI YAML definitions."""
from __future__ import annotations

import argparse
import hashlib
from utils import json
import keyword
from pathlib import Path
import re

from utils import yaml

ROOT = Path(__file__).resolve().parents[2]
METHODS = {'get', 'post', 'put', 'patch', 'delete', 'head', 'options'}
# Existing resource classes retain their validation and convenience methods.
LEGACY = {
    'bank_accounts': ('banking', 'BankAccounts'), 'bank_transactions': ('banking', 'BankTransactions'),
    'bills': ('purchases', 'Bills'), 'chart_of_accounts': ('contacts', 'ChartOfAccounts'),
    'contacts': ('contacts', 'Contacts'), 'credit_notes': ('sales', 'CreditNotes'),
    'customer_payments': ('sales', 'CustomerPayments'), 'estimates': ('sales', 'Estimates'),
    'expenses': ('purchases', 'Expenses'), 'fixed_assets': ('ledger', 'FixedAssets'),
    'invoices': ('sales', 'Invoices'), 'journals': ('banking', 'Journals'),
    'locations': ('contacts', 'Locations'), 'organizations': ('contacts', 'Organizations'),
    'projects': ('projects', 'Projects'), 'purchase_orders': ('purchases', 'PurchaseOrders'),
    'registers': ('ledger', 'Registers'), 'sales_orders': ('sales', 'SalesOrders'),
    'tasks': ('projects', 'Tasks'), 'time_entries': ('projects', 'TimeEntries'),
    'vendor_credits': ('sales', 'VendorCredits'), 'vendor_payments': ('purchases', 'VendorPayments'),
}
ALIASES = {'purchase_order': 'purchase_orders', 'sales_order': 'sales_orders',
           'currency': 'currencies', 'integration': 'integrations',
           'sales_receipt': 'sales_receipts', 'opening_balance': 'opening_balances',
           'base_currency_adjustment': 'base_currency_adjustments'}


def identifier(value: str) -> str:
    value = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', value)
    value = re.sub(r'\W+', '_', value).strip('_').lower()
    if not value or value[0].isdigit() or keyword.iskeyword(value):
        value = 'api_' + value
    return value


def resolve(document: dict, value: dict) -> dict:
    seen = set()
    while '$ref' in value:
        ref = value['$ref']
        if not ref.startswith('#/') or ref in seen:
            raise ValueError(f'Unsupported or cyclic reference: {ref}')
        seen.add(ref)
        value = document
        for part in ref[2:].split('/'):
            value = value[part.replace('~1', '/').replace('~0', '~')]
    return value


def route_key(method: str, path: str) -> tuple[str, str]:
    """Path parameter spelling does not create a different HTTP endpoint."""
    return method, re.sub(r'\{[^}]+\}', '{}', '/' + path.strip('/'))


def custom_route_owners(definitions: dict[str, dict]) -> dict[tuple[str, str], tuple[str, str]]:
    """Discover existing route implementations without issuing HTTP requests.

    Include inherited CRUD/actions, even when an override adds response checks.
    Composite helpers which call these wrappers do not claim another endpoint.
    """
    import ast
    import importlib
    import inspect
    import textwrap
    from types import SimpleNamespace
    from zoho.books.base import BaseResource

    owners = {}
    # Existing owners take precedence over generic CRUD on newly added resources.
    for resource in sorted(definitions, key=lambda n: (n not in LEGACY, n)):
        if resource in LEGACY:
            module, cls = LEGACY[resource]
            resource_type = getattr(importlib.import_module(f'zoho.books.custom.{module}'), cls)
            instance = resource_type(SimpleNamespace())
        else:
            endpoint = next(iter(definitions[resource]['paths'])).strip('/').split('/')[0]
            if '{' in endpoint:
                continue
            instance = BaseResource(SimpleNamespace(), endpoint)
            resource_type = type(instance)
        for base in reversed(resource_type.__mro__):
            for name, member in vars(base).items():
                if name.startswith('_') or not inspect.isfunction(member):
                    continue
                tree = ast.parse(textwrap.dedent(inspect.getsource(member)))
                env = {}

                def value(node):
                    if isinstance(node, ast.Constant):
                        return node.value
                    if isinstance(node, ast.Name):
                        return env.get(node.id, '{' + node.id + '}')
                    if isinstance(node, ast.Subscript):
                        return '{id}'
                    if isinstance(node, ast.Attribute) and node.attr == 'endpoint':
                        return instance.endpoint
                    if isinstance(node, ast.JoinedStr):
                        return ''.join(str(value(n.value)) if isinstance(n, ast.FormattedValue) else str(value(n)) for n in node.values)
                    raise ValueError('Not a static route')

                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        try:
                            resolved = value(node.value)
                            for target in node.targets:
                                if isinstance(target, ast.Name):
                                    env[target.id] = resolved
                        except ValueError:
                            continue
                    if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
                        continue
                    call = node.func
                    try:
                        if call.attr == 'request' and isinstance(call.value, ast.Attribute) and call.value.attr == 'client':
                            method, endpoint = value(node.args[0]), value(node.args[1])
                        elif call.attr == '_action':
                            method, identity, action = [value(n) for n in node.args[:3]]
                            endpoint = f'{instance.endpoint}/{identity}/{action}' if identity else f'{instance.endpoint}/{action}'
                        else:
                            continue
                    except (ValueError, AttributeError, IndexError):
                        continue
                    key = route_key(method, endpoint)
                    previous = owners.get(key)
                    if previous is not None and previous[0] == resource and previous[1] != name:
                        raise ValueError(f'Duplicate custom wrappers for {method} {endpoint}: {previous[1]}, {name}')
                    owners.setdefault(key, (resource, name))
    return owners


def generate(source: Path, destination: Path) -> dict:
    """Validate all definitions before writing generated source and provenance."""
    lines = ['"""Generated by apps/tools/generate_books_sdk.py; do not edit manually."""',
             'from typing import Any', 'from .resource import BooksOperationResource']
    for name, (module, cls) in sorted(LEGACY.items()):
        lines.append(f'from ..custom.{module} import {cls} as Legacy{cls}')
    manifest = {}
    registry = []
    definitions = {}
    for source_file in sorted(source.glob('*.yml')):
        if source_file.stem != 'items':
            key = identifier(source_file.stem)
            definitions[ALIASES.get(key, key)] = yaml.safe_load(source_file.read_bytes())
    owners = custom_route_owners(definitions)
    for path in sorted(source.glob('*.yml')):
        if path.stem == 'items':
            continue  # Item operations belong to Inventory, not Books.
        raw = path.read_bytes()
        document = yaml.safe_load(raw)
        name = identifier(path.stem)
        name = ALIASES.get(name, name)
        if name in manifest:
            raise ValueError(f'Duplicate resource: {name}')
        cls = ''.join(p.title() for p in name.split('_'))
        legacy = LEGACY.get(name)
        bases = f'Legacy{legacy[1]}, BooksOperationResource' if legacy else 'BooksOperationResource'
        lines.extend(['', f'class {cls}({bases}):', f'    """{name} Books API operations."""'])
        if not legacy:
            endpoint = next(iter(document.get('paths', {})), '').strip('/').split('/')[0]
            lines.extend(['    def __init__(self, client: Any) -> None:',
                          f'        super().__init__(client, {endpoint!r})', ''])
        operations = []
        names = set()
        class_start = len(lines)
        for endpoint, item in document.get('paths', {}).items():
            if not endpoint.startswith('/') or '?' in endpoint or '#' in endpoint or '..' in endpoint.split('/'):
                raise ValueError(f'Invalid endpoint: {endpoint}')
            for verb, operation in item.items():
                if verb not in METHODS:
                    continue
                method = identifier(operation['operationId'])
                if method in names or method.startswith('_') or method in {'client', 'endpoint'} or hasattr(object, method):
                    raise ValueError(f'Conflicting operation: {path.name}: {method}')
                names.add(method)
                servers = operation.get('servers', item.get('servers', document.get('servers', [])))
                if not servers or not re.fullmatch(r'https://www\.zohoapis\.(?:com|in|eu|com\.au|jp|ca|com\.cn|sa|ae)/books/v3', servers[0]['url']):
                    raise ValueError(f'Unsupported Books server: {servers}')
                placeholders = list(dict.fromkeys(re.findall(r'\{([^}]+)\}', endpoint)))
                args = [identifier(p) for p in placeholders]
                if len(args) != len(set(args)) or set(args) & {'self', 'body', 'params', 'headers', 'files', 'stream', 'timeout'}:
                    raise ValueError(f'Conflicting path parameters: {endpoint}')
                parameters = {}
                for parameter in item.get('parameters', []) + operation.get('parameters', []):
                    parameter = resolve(document, parameter)
                    parameters[(parameter['in'], parameter['name'])] = parameter
                required = [p['name'] for p in parameters.values() if p['in'] == 'query'
                            and p.get('required') and p['name'] != 'organization_id'
                            and p.get('schema', {}).get('format') != 'binary']
                required_headers = [p['name'] for p in parameters.values() if p['in'] == 'header' and p.get('required')]
                request = resolve(document, operation.get('requestBody', {}))
                media = list(request.get('content', {}))
                # These Books specs omit multipart request bodies on attachment routes
                # and sometimes describe file fields as query parameters instead.
                upload = 'multipart/form-data' in media or (verb in {'post', 'put'} and
                    (endpoint.endswith('/attachment') or any(p.get('schema', {}).get('format') == 'binary' for p in parameters.values())))
                signature = ', '.join(['self'] + [f'{a}: str' for a in args] + ['*',
                    'body: dict[str, Any] | list[dict[str, Any]] | None = None', 'params: dict[str, Any] | None = None',
                    'headers: dict[str, Any] | None = None', 'files: dict[str, Any] | None = None',
                    'stream: bool = False', 'timeout: int | None = None'])
                doc = operation.get('summary', method) + '\n\n' + verb.upper() + ' ' + endpoint
                doc += '\nOAuth scopes: ' + ', '.join(s for scopes in operation.get('security', []) for values in scopes.values() for s in values)
                key = route_key(verb.upper(), endpoint)
                owner = owners.get(key)
                generated = owner is None
                if generated:
                    owner = (name, method)
                    owners[key] = owner
                if generated:
                    lines.extend([f'    def {method}({signature}) -> object:', f'        {doc!r}',
                    f'        return self._request_operation({verb.upper()!r}, {endpoint!r},',
                    f"            path_values={{{', '.join(repr(p) + ': ' + a for p,a in zip(placeholders,args))}}},",
                    f'            required_query={required!r}, required_headers={required_headers!r}, media={media!r},',
                    f'            body_required={bool(request.get("required"))!r}, upload={upload!r}, body=body, params=params,',
                    '            headers=headers, files=files, stream=stream, timeout=timeout)', ''])
                operations.append(dict(name=method, operation_id=operation['operationId'], method=verb.upper(), path=endpoint,
                    path_parameters=placeholders, required_query=required, required_headers=required_headers,
                    media=media, body_required=bool(request.get('required')), upload=upload,
                    wrapper_resource=owner[0], wrapper_name=owner[1], generated=generated))
        if len(lines) == class_start:
            lines.append('    # All documented routes use existing canonical wrappers.')
        if not operations:
            raise ValueError(f'No operations: {path.name}')
        manifest[name] = dict(source=path.name, sha256=hashlib.sha256(raw).hexdigest(), operations=operations)
        registry.append((name, cls))
    if not registry:
        raise ValueError('No Books definitions found')
    lines.extend(['class BooksResources:', '    """Typed generated resources on ZohoBooksAPI."""'])
    lines.extend(f'    {name}: {cls}' for name,cls in registry)
    lines.extend(['', 'RESOURCE_TYPES = {'])
    lines.extend(f'    {name!r}: {cls},' for name,cls in registry)
    lines.append('}\n')
    text = '\n'.join(lines)
    compile(text, 'generated.py', 'exec')
    destination.mkdir(parents=True, exist_ok=True)
    (destination / 'generated.py').write_text(text, encoding='utf-8', newline='\n')
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n', encoding='utf-8', newline='\n')
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    manifest = generate(args.source, ROOT / 'src/zoho/books/openapi')
    print(f'Generated {len(manifest)} resources and {sum(len(v["operations"]) for v in manifest.values())} operation records (items excluded).')


if __name__ == '__main__':
    main()

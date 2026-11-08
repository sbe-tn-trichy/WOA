"""Books OpenAPI coverage, additive compatibility and wire safety."""
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from zoho.books import ZohoBooksAPI
from zoho.books.openapi import RESOURCE_TYPES
from zoho.core_sdk.base_resource import BaseResource

ROOT = Path(__file__).resolve().parents[3]
MANIFEST = json.loads((ROOT / 'src/zoho/books/openapi/manifest.json').read_text())
OPERATIONS = [(r,o) for r,v in MANIFEST.items() for o in v['operations']]
GENERATED = [(r,o) for r,o in OPERATIONS if o['generated']]


@pytest.fixture
def api():
    with ZohoBooksAPI('offline', 'org', domain='in') as client:
        yield client


@pytest.mark.parametrize('resource,operation', GENERATED,
                         ids=[f'{r}.{o["name"]}' for r,o in GENERATED])
def test_every_operation_routes_through_books_transport(api, resource, operation):
    params = {n: 'value' for n in operation['required_query']}
    headers = {n: 'value' for n in operation['required_headers']}
    args = ['id /?#'] * len(operation['path_parameters'])
    with patch('zoho.core_sdk.base_client.BaseZohoClient.request', return_value={'code': 0}) as request:
        result = getattr(getattr(api,resource),operation['name'])(
            *args, body={} if operation['body_required'] else None,
            params=params, headers=headers, timeout=11, stream=True)
    assert result == {'code': 0}
    expected = operation['path']
    for name in operation['path_parameters']:
        expected = expected.replace('{'+name+'}', 'id%20%2F%3F%23')
    wire = request.call_args.kwargs
    assert wire['method'] == operation['method']
    assert wire['endpoint'] == expected.lstrip('/')
    assert wire['params'] == {**params, 'organization_id': 'org'}
    assert wire['timeout'] == 11 and wire['stream'] is True
    assert params == {n: 'value' for n in operation['required_query']}


def test_inventory_exclusion_and_existing_methods(api):
    assert len(MANIFEST) == len(RESOURCE_TYPES) == 44
    assert len(OPERATIONS) == 854
    assert not hasattr(api, 'items')
    assert isinstance(api.invoices, BaseResource)
    for r,o in OPERATIONS:
        assert callable(getattr(getattr(api,o['wrapper_resource']),o['wrapper_name']))
        if o['generated']:
            hierarchy = type(getattr(api, r)).__mro__
            assert sum(o['name'] in vars(base) for base in hierarchy) == 1
    from zoho.books.custom.purchases import Bills
    from zoho.books.custom.ledger import Registers
    assert isinstance(api.bills, Bills)
    assert isinstance(api.registers, Registers)
    with patch.object(api, 'request', return_value={'code': 0}) as request:
        api.invoices.mark_as_sent('id')
        request.assert_called_once_with('POST','invoices/id/status/sent',json=None,params=None)
    assert callable(api.contacts.list_customers)
    assert callable(api.sales_orders.add_attachment)
    assert callable(api.vendor_payments.update_with_number_series)


@pytest.mark.parametrize('value', ['', ' ', '.', '..', None, 42])
def test_invalid_path_blocks_network(api, value):
    r,o = next((r,o) for r,o in GENERATED if o['path_parameters'])
    with patch.object(api,'request') as request:
        with pytest.raises(ValueError, match='path identifier'):
            getattr(getattr(api,r),o['name'])(*[value]*len(o['path_parameters']))
        request.assert_not_called()


def test_query_scope_and_body_validation(api):
    r,o = next((r,o) for r,o in GENERATED if o['required_query'])
    with patch.object(api,'request') as request:
        with pytest.raises(ValueError, match='required query'):
            getattr(getattr(api,r),o['name'])(*['id']*len(o['path_parameters']))
        with pytest.raises(ValueError, match='organization'):
            api.invoices.get_invoice_email('id',params={'organization_id':'other'})
        with pytest.raises(ValueError, match='request body'):
            api.invoices.get_invoice_email('id',body={})
        with pytest.raises(ValueError, match='multipart'):
            api.invoices.get_invoice_email('id',files={'attachment':b'x'})
        request.assert_not_called()


def test_upload_encoding_and_array_body(api):
    files = {'attachment': ('file.txt', b'content')}
    # Legacy upload definitions describe files as query parameters; accept files.
    r,o = next((r,o) for r,o in OPERATIONS if r=='invoices' and o['method']=='POST' and o['path'].endswith('/attachment'))
    with patch.object(api,'request') as request:
        getattr(api.invoices,o['name'])('id',files=files)
        assert request.call_args.kwargs['files'] is files
        assert request.call_args.kwargs['json'] is None
    r,o = next((r,o) for r,o in OPERATIONS if 'multipart/form-data' in o['media'])
    with patch.object(api,'request') as request:
        getattr(getattr(api,r),o['name'])(*['id']*len(o['path_parameters']),body={'can_send_in_mail':True},files=files,
            params={n:'value' for n in o['required_query']})
        assert request.call_args.kwargs['data'] == {'can_send_in_mail':True}
    r,o = next((r,o) for r,o in OPERATIONS if r=='tasks' and o['method']=='POST' and o['path']=='/tasks')
    with patch.object(api,'request') as request:
        getattr(api.tasks,o['wrapper_name'])([{'task_name':'Example'}], params={n:'value' for n in o['required_query']})
        assert request.call_args.kwargs['json'] == [{'task_name':'Example'}]


def test_generator_is_deterministic_and_rejects_invalid_input(tmp_path):
    spec = importlib.util.spec_from_file_location('generate_books_sdk', ROOT/'apps/tools/generate_books_sdk.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path/'specs'
    source.mkdir()
    f = source/'example.yml'
    f.write_text('''openapi: 3.0.0
servers:
  - url: https://www.zohoapis.com/books/v3
paths:
  /examples/{id}:
    get:
      operationId: get_example
''')
    target = tmp_path/'generated'
    module.generate(source,target)
    def snapshot():
        return {path.relative_to(target): path.read_bytes()
                for path in target.rglob('*') if path.is_file()}

    first = snapshot()
    module.generate(source,target)
    assert snapshot() == first
    f.write_text(f.read_text().replace('www.zohoapis.com','example.com'))
    with pytest.raises(ValueError,match='server'):
        module.generate(source,target)
    assert snapshot() == first


def test_generated_layout_limits_and_resource_imports():
    from zoho.books.openapi.generated import Contacts, CreditNotes, Invoices

    package = ROOT / 'src/zoho/books/openapi'
    generated = [package / 'generated.py', *(package / 'resources').rglob('*.py')]
    assert len(generated) > len(RESOURCE_TYPES)
    for path in generated:
        assert len(path.read_text(encoding='utf-8').splitlines()) <= 400, path
    for directory in {path.parent for path in generated}:
        assert sum(path.is_file() for path in directory.iterdir()) <= 10, directory
    for name, cls in [('contacts', Contacts), ('credit_notes', CreditNotes), ('invoices', Invoices)]:
        assert RESOURCE_TYPES[name] is cls
        assert cls.__module__.startswith('zoho.books.openapi.resources.')


def test_one_canonical_wrapper_per_http_route(api):
    import re
    owners = {}
    emitted = set()
    for _, operation in OPERATIONS:
        key = (operation['method'], re.sub(r'\{[^}]+\}', '{}', operation['path']))
        owner = (operation['wrapper_resource'], operation['wrapper_name'])
        assert owners.setdefault(key, owner) == owner
        if operation['generated']:
            assert key not in emitted
            emitted.add(key)
    assert len(owners) == 843
    assert len(emitted) == 629
    assert not hasattr(api.invoices, 'get_invoice')
    assert not hasattr(api.invoices, 'list_invoices')
    assert not hasattr(api.bills, 'update_bill')
    assert callable(api.invoices.get)
    assert callable(api.invoices.list)
    assert callable(api.bills.update)


def test_number_series_preparation_uses_single_update_wrapper(api):
    payload = {'location_id':'loc','payment_number_prefix':'P-','payment_number_suffix':'1'}
    for resource in [api.customer_payments, api.vendor_payments]:
        with patch.object(resource,'update',return_value={'code':0}) as update:
            assert resource.update_with_number_series('id',payload) == {'code':0}
            update.assert_called_once()
            assert update.call_args.args == ('id', {})
            assert json.loads(update.call_args.kwargs['files']['JSONString'][1]) == payload


def test_download_uses_single_statement_wrapper(api, tmp_path):
    from unittest.mock import Mock
    response = Mock()
    response.iter_content.return_value = [b'document']
    with patch.object(api.contacts,'get_statement',return_value=response) as get:
        api.contacts.download_statement('id',str(tmp_path/'statement.xls'))
    get.assert_called_once_with('id',params={'accept':'xls'},stream=True)
    assert (tmp_path/'statement.xls').read_bytes() == b'document'
    response.close.assert_called_once()


def test_generation_deduplicates_existing_and_cross_file_routes(tmp_path):
    spec = importlib.util.spec_from_file_location('books_dedup_generator',ROOT/'apps/tools/generate_books_sdk.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    source = tmp_path/'source'
    source.mkdir()
    template = '''openapi: 3.0.0
servers:
  - url: https://www.zohoapis.com/books/v3
paths:
  /invoices/{identifier}:
    get:
      operationId: get_copy
  /unique/{identifier}/action:
    post:
      operationId: do_action
'''
    (source/'invoices.yml').write_text(template.replace('{identifier}','{invoice_id}'))
    (source/'copy.yml').write_text(template.replace('{identifier}','{copy_id}'))
    manifest = module.generate(source,tmp_path/'target')
    gets = [o for v in manifest.values() for o in v['operations'] if o['method']=='GET']
    assert {(o['wrapper_resource'],o['wrapper_name']) for o in gets} == {('invoices','get')}
    assert not any(o['generated'] for o in gets)
    actions = [o for v in manifest.values() for o in v['operations'] if o['method']=='POST']
    assert sum(o['generated'] for o in actions) == 1
    assert len({(o['wrapper_resource'],o['wrapper_name']) for o in actions}) == 1
    text = '\n'.join(path.read_text() for path in (tmp_path/'target/resources').rglob('*.py'))
    assert 'def get_copy(' not in text
    assert text.count('def do_action(') == 1


def test_generator_rejects_duplicate_custom_http_wrappers(monkeypatch):
    from zoho.books.custom.sales import Invoices
    spec = importlib.util.spec_from_file_location('books_conflict_generator',ROOT/'apps/tools/generate_books_sdk.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def duplicate_list(self):
        return self.client.request('GET', self.endpoint)

    monkeypatch.setattr(Invoices,'duplicate_list',duplicate_list,raising=False)
    with pytest.raises(ValueError,match='Duplicate custom wrappers'):
        module.custom_route_owners({'invoices':{'paths':{'/invoices':{}}}})

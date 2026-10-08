import os, sys, re, json, inspect, importlib
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'erp_backend.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import django
django.setup()

from django.urls import URLResolver, get_resolver, resolve, Resolver404
from rest_framework import serializers

HTTP_METHODS = ['get', 'post', 'put', 'patch', 'delete']

# ---------------------------------------------------------------- url crawl
def collect(patterns, prefix='', stack=()):
    out = []
    for p in patterns:
        if isinstance(p, URLResolver):
            out += collect(p.url_patterns, prefix + str(p.pattern),
                           stack + (str(getattr(p, 'pattern', '')),))
        else:
            out.append(prefix + str(p.pattern))
    return out

raw_urls = sorted({u for u in collect(get_resolver().url_patterns) if u.startswith('api')})

path_param = re.compile(r'<(?:(\w+):)?(\w+)>')
named_group = re.compile(r'\(\?P<(\w+)>([^)]+)\)')

def to_postman_path(regex):
    """Return a Postman-style path (with :vars) or None for format-suffix duplicates."""
    if 'format' in [g[0] for g in named_group.findall(regex)]:
        return None
    if re.search(r'<[^>]*format[^>]*>', regex):
        return None
    if named_group.search(regex):
        s = named_group.sub(lambda m: ':' + m.group(1), regex)
        if '(' in s or ')' in s or '\\' in s:
            return None
    elif '<' in regex:
        if '(' in regex or '\\' in regex:
            return None
        s = path_param.sub(lambda m: ':' + (m.group(2) or m.group(1)), regex)
    else:
        s = regex
    return s.replace('^', '').replace('$', '').rstrip('?')

def to_concrete(path):
    out = []
    for seg in path.split('/'):
        if seg.startswith(':'):
            name = seg[1:]
            out.append('1' if name in ('pk', 'id') or name.endswith('_id') else 'sample')
        else:
            out.append(seg)
    return '/'.join(out)

# ------------------------------------------------------------- view lookup
def unwrap(cb):
    """Return (view_class, action_name-map)."""
    action_map = dict(getattr(cb, 'actions', None) or {})
    if not action_map:
        for k, v in (getattr(cb, 'initkwargs', None) or {}).items():
            if k in HTTP_METHODS:
                action_map[k] = v
    cls = getattr(cb, 'cls', None) or getattr(cb, 'view_class', None)
    if not action_map and cls:
        for m in HTTP_METHODS:
            if hasattr(cls, m) and m in getattr(cls, 'http_method_names', HTTP_METHODS):
                action_map[m] = m
    return cls, action_map

APP_NAMES = {
    'authentication': 'Auth & Users', 'organization': 'Organization',
    'core': 'Core & Settings', 'crm': 'CRM & Sales', 'projects': 'Projects',
    'designer': 'Design & Engineering', 'purchase': 'Purchase',
    'store': 'Store & Inventory', 'production': 'Production',
    'maintenance': 'Maintenance & Service', 'hr': 'HR & Payroll',
    'accounting': 'Accounting & Finance', 'integration': 'Integration & Dashboards',
}
APP_PREFIX = {
    'authentication': 'auth', 'organization': 'org', 'core': 'core', 'crm': 'crm',
    'projects': 'projects', 'designer': 'designer', 'purchase': 'purchase',
    'store': 'store', 'production': 'production', 'maintenance': 'maintenance',
    'hr': 'hr', 'accounting': 'accounting', 'integration': 'integration',
}

def folder_for(cls, path):
    if cls is not None:
        mod = inspect.getmodule(cls)
        if mod and mod.__name__.startswith('apps.'):
            app = mod.__name__.split('.')[1]
            return APP_NAMES.get(app, app.title())
    seg = path.strip('/').split('/')
    if len(seg) < 2 or not seg[1]:
        return 'Meta'
    alias = {'auth': 'authentication', 'org': 'organization'}
    key = alias.get(seg[1], seg[1])
    return APP_NAMES.get(key, seg[1].title())

# ---------------------------------------------------------- sample payloads
def sample_value(name, field, depth=0):
    n = (name or '').lower()
    if isinstance(field, serializers.ListSerializer):
        child = field.child
        if isinstance(child, serializers.BaseSerializer):
            return [sample_object(child, depth + 1)] if depth < 2 else []
        return [sample_value(child.source or name, child, depth + 1)]
    if isinstance(field, serializers.BaseSerializer):
        return sample_object(field, depth + 1) if depth < 2 else {}
    if isinstance(field, serializers.BooleanField):
        return True
    if isinstance(field, serializers.IntegerField):
        return 1
    if isinstance(field, (serializers.FloatField, serializers.DecimalField)):
        return 1.0
    if isinstance(field, serializers.DateTimeField):
        return '2026-01-15T10:00:00'
    if isinstance(field, serializers.DateField):
        return '2026-01-15'
    if isinstance(field, serializers.TimeField):
        return '10:00:00'
    if isinstance(field, serializers.JSONField):
        return {} if not n.endswith('s') else []
    if isinstance(field, serializers.URLField):
        return 'https://example.com'
    if isinstance(field, serializers.EmailField):
        return 'user@example.com'
    choices = getattr(field, 'choices', None)
    if choices:
        try:
            return list(choices.keys())[0]
        except Exception:
            pass
    if 'username' in n:
        return 'admin'
    if 'password' in n:
        return 'change-me@123'
    if 'email' in n:
        return 'user@example.com'
    if 'mobile' in n or 'phone' in n:
        return '+91 98765 43210'
    if n in ('website', 'url', 'link'):
        return 'https://example.com'
    if n.endswith(('_at', 'datetime')):
        return '2026-01-15T10:00:00'
    if n.endswith('_date') or n == 'date':
        return '2026-01-15'
    if n.endswith('_id') or n in ('customer_id', 'project_id', 'job_id'):
        return 'REF-001'
    if isinstance(field, serializers.MultipleChoiceField):
        return []
    if n.endswith(('amount', 'qty', 'quantity', '_total', '_count', '_rate', '_price', '_value')):
        return 1.0
    return ''

def sample_object(ser, depth=0):
    body = {}
    for name, field in ser.fields.items():
        if getattr(field, 'read_only', False):
            continue
        if name in ('id', 'pk'):
            continue
        body[name] = sample_value(name, field, depth)
    return body

def serializer_for(cls, action_name):
    if cls is None:
        return None
    if action_name in ('list', 'retrieve'):
        return None
    try:
        inst = cls()
    except Exception:
        return None
    if action_name and hasattr(inst, 'action'):
        try:
            inst.action = action_name
        except Exception:
            pass
    try:
        return inst.get_serializer_class()
    except Exception:
        return getattr(cls, 'serializer_class', None)

GET_SOURCE = re.compile(r"query_params\.get\(\s*['\"](\w+)['\"]")
POST_SOURCE = re.compile(r"request\.data\.get\(\s*['\"](\w+)['\"]")

def camel_to_snake(s):
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', s)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower()

SNK = camel_to_snake

def dedupe_keys(keys):
    seen, out = {}, []
    for k in keys:
        s = SNK(k)
        if s not in seen:
            seen[s] = True
            out.append(s)
    return out

VERBS = {
    'list': ('List', 's'),
    'retrieve': ('Get', ''),
    'create': ('Create', ''),
    'update': ('Update', ''),
    'partial_update': ('Update', ' (Partial)'),
    'destroy': ('Delete', ''),
}

def request_name(cls, action_name, initkwargs):
    base = (initkwargs or {}).get('basename') or ''
    res = base.replace('-', ' ').strip().replace('_', ' ').title()
    if not res and cls is not None:
        cname = cls.__name__
        for suf in ('APIView', 'ViewSet', 'BaseView', 'Set', 'View'):
            if cname.endswith(suf):
                cname = cname[:-len(suf)]
                break
        cname = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', cname)
        cname = re.sub(r'([A-Z]{2,})([A-Z])', r'\1 \2', cname)
        res = cname.title()
    if not res:
        res = 'Resource'

    if action_name == 'list':
        return 'List %s' % (res + 's' if not res.endswith('s') else res)
    if action_name == 'partial_update':
        return 'Update %s (Partial)' % res
    if action_name in ('retrieve', 'create', 'update', 'destroy'):
        verb = {'retrieve': 'Get', 'create': 'Create', 'update': 'Update', 'destroy': 'Delete'}[action_name]
        return '%s %s' % (verb, res)
    if action_name in HTTP_METHODS:
        return '%s [%s]' % (res, action_name.upper())
    return '%s: %s' % (res, action_name.replace('_', ' ').title())

def source_of(cls, action_name, method):
    if cls is None:
        return ''
    fn = getattr(cls, action_name, None) or getattr(cls, method, None)
    if fn is None:
        return ''
    try:
        return inspect.getsource(fn)
    except Exception:
        return ''

# ---------------------------------------------------------------- build it
raw_records = []
seen = set()
count = 0

for raw in raw_urls:
    path = to_postman_path(raw)
    if path is None:
        continue
    concrete = to_concrete(path)
    try:
        match = resolve('/' + concrete)
    except (Resolver404, Exception):
        continue
    cb = match.func
    cls, action_map = unwrap(cb)
    initkwargs = getattr(cb, 'initkwargs', {}) or {}
    if not action_map:
        action_map = {'get': 'list'}

    key = (path, tuple(sorted(action_map)))
    if key in seen:
        continue
    seen.add(key)

    folder = folder_for(cls, path)

    # path variable samples (real ids where available)
    variables = []
    for seg in path.split('/'):
        if not seg.startswith(':'):
            continue
        name = seg[1:]
        value = '1' if name in ('pk', 'id') else 'sample'
        if name in ('pk', 'id') and cls is not None:
            try:
                inst = cls()
                qs = inst.get_queryset()
                obj = qs.order_by().first()
                if obj is not None:
                    value = str(obj.pk)
            except Exception:
                pass
        variables.append({'key': name, 'value': value})

    query = []
    items = []
    for method in HTTP_METHODS:
        if method not in action_map:
            continue
        action_name = action_map[method]
        count += 1

        qkeys = dedupe_keys(GET_SOURCE.findall(source_of(cls, action_name, method)))
        query = [{'key': k, 'value': '', 'description': 'query parameter'} for k in qkeys]

        body = None
        body_note = None
        if method in ('post', 'put', 'patch'):
            ser = None
            if action_name in ('create', 'update', 'partial_update'):
                ser = serializer_for(cls, action_name)
            if ser is not None:
                try:
                    body = sample_object(ser())
                    body_note = 'Request body generated from serializer fields (' + ser.__name__ + ').'
                except Exception:
                    body = None
            if body is None:
                dkeys = dedupe_keys(POST_SOURCE.findall(source_of(cls, action_name, method)))
                if dkeys:
                    body = {k: sample_value(k, serializers.CharField()) for k in dkeys}
                    body_note = 'Sample body from keys read via request.data.get() in the action source.'

        desc_parts = []
        if cls is not None:
            desc_parts.append('View: %s.%s' % (cls.__name__, action_name))
        if body_note:
            desc_parts.append(body_note)
        desc_parts.append('Endpoint: {{base_url}}/' + path)
        name = request_name(cls, action_name, initkwargs)
        request = {
            'method': method.upper(),
            'header': [{'key': 'Accept', 'value': 'application/json'}],
            'url': {
                'raw': '{{base_url}}/' + path + ('?' + '&'.join('%s=' % q['key'] for q in query) if query else ''),
                'host': ['{{base_url}}'],
                'path': [s for s in path.strip('/').split('/')],
            },
            'description': ' '.join(desc_parts),
        }
        if variables:
            request['url']['variable'] = [{'key': v['key'], 'value': v['value']} for v in variables]
        if query:
            request['url']['query'] = query
        if path.rstrip('/').endswith(('login', 'token/refresh', 'refresh')) or '/auth/login' in path:
            request['auth'] = {'type': 'noauth'}
        if body is not None:
            request['header'].append({'key': 'Content-Type', 'value': 'application/json'})
            request['body'] = {'mode': 'raw', 'raw': json.dumps(body, indent=2),
                               'options': {'raw': {'language': 'json'}}}

        items.append({
            'name': name,
            'request': request,
            'response': [],
        })

        cid = '%s.%s' % (cls.__module__, cls.__name__) if cls is not None else 'path:' + path
        slug = path.strip('/').split('/')[1] if len(path.strip('/').split('/')) > 1 else ''
        app = cls.__module__.split('.')[1] if cls is not None and cls.__module__.startswith('apps.') else None
        raw_records.append((folder, cid, app, slug, method, path, items[-1]))

# ---------------- dedupe root-router twins (prefer namespaced api/<app>/…)
groups = {}
for folder, cid, app, slug, method, path, item in raw_records:
    key = (cid, method) if app else (cid, method, slug)
    groups.setdefault(key, []).append((folder, slug, path, item))

chosen = []
for key, grp in groups.items():
    app = None
    cid = key[0]
    if cid.startswith('apps.'):
        app = cid.split('.')[1]
    if app:
        prefix = APP_PREFIX.get(app)
        keep = [g for g in grp if g[1] == prefix] or grp
    else:
        keep = grp
    chosen.extend(keep)

uniq = {}
for folder, slug, path, item in chosen:
    k = (path, item['request']['method'])
    if k not in uniq:
        uniq[k] = (folder, slug, path, item)
chosen = list(uniq.values())

folders = {}
for folder, slug, path, item in chosen:
    folders.setdefault(folder, []).append(item)

# ------------------------------------------------------------------ output
deduped = len(chosen)
collection = {
    'info': {
        'name': 'BE-ERP-UMA — UmaERP API Collection',
        'description': (
            'Auto-generated collection for the BE-ERP-UMA Django REST backend.\n\n'
            '**Setup**\n'
            '1. Set the `base_url` variable (default `http://127.0.0.1:8000`).\n'
            '2. Call `Login [POST]` with username/password, then copy the '
            'returned `access` token into the `jwt_token` variable.\n'
            '3. All other requests inherit `Authorization: Bearer {{jwt_token}}`.\n\n'
            '**Notes**\n'
            '- Request bodies use the exact field names declared by each DRF serializer. '
            'The API accepts snake_case keys; camelCase aliases are echoed in responses.\n'
            '- When a route is registered both on the root router and on the per-app '
            'router (e.g. `/api/sales-invoices/` and `/api/accounting/sales-invoices/`), '
            'the namespaced per-app URL is kept and the duplicate dropped.\n'
            '- `:pk` style path variables are pre-filled with a real record id from the '
            'local database when one exists.\n'
            '- Endpoints with no body (list/retrieve/actions) are sent as plain GET/POST.'
        ),
        'schema': 'https://schema.getpostman.com/json/collection/v2.1.0/collection.json',
    },
    'auth': {
        'type': 'bearer',
        'bearer': [{'key': 'token', 'value': '{{jwt_token}}', 'type': 'string'}],
    },
    'header': [
        {'key': 'Content-Type', 'value': 'application/json'},
        {'key': 'Accept', 'value': 'application/json'},
    ],
    'variable': [
        {'key': 'base_url', 'value': 'http://127.0.0.1:8000', 'type': 'string'},
        {'key': 'jwt_token', 'value': '', 'type': 'string'},
    ],
    'item': [
        {'name': f, 'item': sorted(folders[f], key=lambda i: i['name'])}
        for f in sorted(folders, key=lambda x: (x == 'Meta', x))
    ],
}

out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'UmaERP.postman_collection.json')
with open(out_path, 'w', encoding='utf-8') as fh:
    json.dump(collection, fh, indent=2, ensure_ascii=False)

print('urls seen: %d   requests: %d  (dropped %d root-router duplicates)' % (count, len(chosen), count - len(chosen)))
print('folders: %d' % len(folders))
for f in sorted(folders, key=lambda x: (x == 'Meta', x)):
    print('  %-30s %d' % (f, len(folders[f])))
print('written ->', out_path)

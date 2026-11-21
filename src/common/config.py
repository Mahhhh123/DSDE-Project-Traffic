import datetime
import json
import os
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open(os.path.join(ROOT, 'configs', 'settings.yaml'), encoding='utf-8') as _f:
    CFG = yaml.safe_load(_f)


def path(key, *parts):
    base = os.path.expanduser(CFG['paths'][key])
    if not os.path.isabs(base):
        base = os.path.join(ROOT, base)
    full = os.path.join(base, *parts)
    target = os.path.dirname(full) if parts else full
    if not os.path.splitext(target)[1]:
        os.makedirs(target, exist_ok=True)
    return full


def days():
    d = datetime.date.fromisoformat(str(CFG['period']['start']))
    end = datetime.date.fromisoformat(str(CFG['period']['end']))
    while d <= end:
        yield d
        d += datetime.timedelta(days=1)


def period_of(hour):
    return 'เช้า' if hour < 9 else 'สาย' if hour < 12 else 'บ่าย' if hour < 16 else 'เย็น' if hour < 19 else 'ค่ำ'


def write_json(obj, *parts, key='reports'):
    p = path(key, *parts)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, default=str)
    return p


def read_json(*parts, key='reports'):
    with open(path(key, *parts), encoding='utf-8') as f:
        return json.load(f)


def arg(name, default=None):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else default

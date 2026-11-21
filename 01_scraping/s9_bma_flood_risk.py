import csv
import io
import json
import os

from common import CLEAN, fetch

API = 'https://data.bangkok.go.th/api/3/action/package_show?id=%s'
DATASETS = {
    'flood_risk': 'flood_risk_points.csv',
    'flood_risk26': 'flood_risk_points_2568.csv',
    'frd_dds': 'road_flood_events_2566.csv',
}


def resource_url(package):
    meta = json.loads(fetch(API % package, 'bma_open_data'))['result']
    csvs = [r for r in meta['resources'] if (r.get('format') or '').upper() == 'CSV' and r.get('url')]
    return csvs[0]['url'], meta['metadata_modified']


def download(url):
    import urllib.request
    from common import UA, log
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=90) as r:
        raw = r.read()
        log('bma_open_data', url, r.status, len(raw))
    for enc in ('utf-8-sig', 'cp874'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'replace')


def main():
    for package, name in DATASETS.items():
        url, modified = resource_url(package)
        text = download(url)
        rows = list(csv.reader(io.StringIO(text)))
        with open(os.path.join(CLEAN, name), 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerows(rows)
        print(package, '→', name, len(rows) - 1, 'rows · updated', modified[:10])


if __name__ == '__main__':
    main()

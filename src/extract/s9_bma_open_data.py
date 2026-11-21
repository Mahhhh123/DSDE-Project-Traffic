import json

from src.extract.http import fetch

API = 'https://data.bangkok.go.th/api/3/action/package_show?id=%s'
PACKAGES = ['flood_risk', 'flood_risk26', 'frd_dds']


def main():
    for p in PACKAGES:
        meta = json.loads(fetch(API % p, 'bma_open_data', '%s_meta.json' % p, check_robots=False))['result']
        res = [r for r in meta['resources'] if (r.get('format') or '').upper() == 'CSV' and r.get('url')][0]
        raw = fetch(res['url'], 'bma_open_data', '%s.csv' % p, check_robots=False)
        print(p, len(raw), 'bytes, modified', meta['metadata_modified'][:10])


if __name__ == '__main__':
    main()

import csv

from src.common.config import path
from src.extract.http import fetch

ENDPOINTS = ['https://maps.mail.ru/osm/tools/overpass/api/interpreter', 'https://overpass-api.de/api/interpreter']


def bbox():
    rows = [r for r in csv.DictReader(open(path('cctv_info'), encoding='utf-8-sig')) if r['latitude']]
    la, lo = [float(r['latitude']) for r in rows], [float(r['longitude']) for r in rows]
    return '%.4f,%.4f,%.4f,%.4f' % (min(la) - 0.01, min(lo) - 0.01, max(la) + 0.01, max(lo) + 0.01)


def query(q, file):
    for ep in ENDPOINTS:
        try:
            return fetch(ep, 'osm', file, data={'data': q}, delay=3.0, check_robots=False)
        except Exception as e:
            print('endpoint failed', ep, type(e).__name__)
    raise RuntimeError('overpass failed')


def main():
    b = bbox()
    query('[out:json][timeout:180];(nwr[shop~"^(mall|department_store)$"](%s);'
          'nwr[amenity~"^(marketplace|townhall|school|university|college|restaurant|cafe|fast_food|hospital|clinic)$"](%s);'
          'nwr[office](%s);nwr[railway=station](%s);node[highway=bus_stop](%s););out center tags;' % ((b,) * 5), 'poi.json')
    query('[out:json][timeout:180];way[highway~"^(motorway|trunk|primary|secondary|tertiary)$"](%s);out tags geom;' % b, 'major_roads.json')
    print('osm done bbox', b)


if __name__ == '__main__':
    main()

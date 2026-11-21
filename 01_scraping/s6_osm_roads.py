import csv
import json
import math
import os

from common import CLEAN, RAW, ROOT, fetch

ENDPOINTS = ['https://maps.mail.ru/osm/tools/overpass/api/interpreter', 'https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter']
RANK = ['motorway', 'trunk', 'primary', 'secondary', 'tertiary']
RADIUS = 300
ROAD_RADIUS = 60
POI_RULES = [
    ('mall', lambda t: t.get('shop') in ('mall', 'department_store')),
    ('market', lambda t: t.get('amenity') == 'marketplace'),
    ('government', lambda t: t.get('office') == 'government' or t.get('amenity') == 'townhall'),
    ('office', lambda t: 'office' in t and t.get('office') != 'government'),
    ('school', lambda t: t.get('amenity') in ('school', 'university', 'college')),
    ('rail_station', lambda t: t.get('railway') == 'station'),
    ('bus_stop', lambda t: t.get('highway') == 'bus_stop'),
    ('food', lambda t: t.get('amenity') in ('restaurant', 'cafe', 'fast_food')),
    ('hospital', lambda t: t.get('amenity') in ('hospital', 'clinic')),
]


def haversine(a, b, c, d):
    a, b, c, d = map(math.radians, (a, b, c, d))
    return 6371000 * 2 * math.asin(math.sqrt(math.sin((c - a) / 2) ** 2 + math.cos(a) * math.cos(c) * math.sin((d - b) / 2) ** 2))


def point_segment(p, a, b):
    k = math.cos(math.radians(p[0]))
    ax, ay, bx, by, px, py = a[1] * k, a[0], b[1] * k, b[0], p[1] * k, p[0]
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return haversine(p[0], p[1], ay + t * dy, (ax + t * dx) / k)


def query(q, name):
    path = os.path.join(RAW, name)
    if os.path.exists(path):
        return json.load(open(path, encoding='utf-8'))
    for ep in ENDPOINTS:
        try:
            d = json.loads(fetch(ep, 'overpass', data={'data': q}, delay=3.0, tries=2))
            json.dump(d, open(path, 'w', encoding='utf-8'))
            return d
        except Exception as e:
            print('  endpoint failed', ep, type(e).__name__)
    raise RuntimeError('all overpass endpoints failed')


def main():
    cams = list(csv.DictReader(open(os.path.join(ROOT, 'data', 'cameras.csv'), encoding='utf-8')))
    lats, lons = [float(c['lat']) for c in cams], [float(c['lon']) for c in cams]
    bbox = '%.4f,%.4f,%.4f,%.4f' % (min(lats) - 0.01, min(lons) - 0.01, max(lats) + 0.01, max(lons) + 0.01)
    poi = query('[out:json][timeout:180];(nwr[shop~"^(mall|department_store)$"](%s);nwr[amenity~"^(marketplace|townhall|school|university|college|restaurant|cafe|fast_food|hospital|clinic)$"](%s);'
                'nwr[office](%s);nwr[railway=station](%s);node[highway=bus_stop](%s););out center tags;' % ((bbox,) * 5), 'osm_poi.json')
    roads = query('[out:json][timeout:180];way[highway~"^(motorway|trunk|primary|secondary|tertiary)$"](%s);out tags geom;' % bbox, 'osm_major_roads.json')
    pois = []
    for e in poi['elements']:
        lat, lon = (e['lat'], e['lon']) if 'lat' in e else (e.get('center', {}).get('lat'), e.get('center', {}).get('lon'))
        if lat is None:
            continue
        cat = next((n for n, rule in POI_RULES if rule(e.get('tags', {}))), None)
        if cat:
            pois.append((cat, lat, lon))
    ways = [(w['tags'], [(g['lat'], g['lon']) for g in w.get('geometry', [])]) for w in roads['elements'] if w.get('geometry')]
    out = []
    for c in cams:
        p = (float(c['lat']), float(c['lon']))
        counts = {n: 0 for n, _ in POI_RULES}
        for cat, la, lo in pois:
            if abs(la - p[0]) < 0.004 and abs(lo - p[1]) < 0.004 and haversine(p[0], p[1], la, lo) <= RADIUS:
                counts[cat] += 1
        near = []
        for tags, geom in ways:
            if not any(abs(la - p[0]) < 0.002 and abs(lo - p[1]) < 0.002 for la, lo in geom):
                continue
            d = min(point_segment(p, a, b) for a, b in zip(geom, geom[1:]))
            if d <= ROAD_RADIUS:
                near.append((RANK.index(tags['highway']), d, tags))
        best = min(near, key=lambda x: (x[0], x[1]))[2] if near else {}
        row = {'cam': c['cam'], 'road_name': best.get('name', ''), 'highway': best.get('highway', 'minor'), 'lanes': best.get('lanes', ''), 'oneway': best.get('oneway', '')}
        row.update({'poi_%s_%dm' % (k, RADIUS): v for k, v in counts.items()})
        out.append(row)
    with open(os.path.join(CLEAN, 'osm_camera_context.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print('pois', len(pois), 'major road ways', len(ways), 'cameras', len(out))


if __name__ == '__main__':
    main()

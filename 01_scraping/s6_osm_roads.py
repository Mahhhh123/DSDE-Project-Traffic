import csv, json, os
from common import fetch, CLEAN, ROOT
ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.private.coffee/api/interpreter', 'https://maps.mail.ru/osm/tools/overpass/api/interpreter']
Q = '[out:json][timeout:60];(way(around:40,{lat},{lon})[highway];)->.r;.r out tags;\n(node(around:300,{lat},{lon})[railway=station];node(around:300,{lat},{lon})[amenity=school];way(around:300,{lat},{lon})[amenity=school];\n node(around:300,{lat},{lon})[shop=mall];way(around:300,{lat},{lon})[shop=mall];);out count;'
RANK = ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'unclassified', 'residential', 'service']

def query(q):
    for ep in ENDPOINTS:
        try:
            return json.loads(fetch(ep, 'overpass', data={'data': q}, delay=2.0, tries=1))
        except Exception as e:
            print('  endpoint failed', ep, type(e).__name__)
    raise RuntimeError('all overpass endpoints failed')

def main():
    cams = list(csv.DictReader(open(os.path.join(ROOT, 'data', 'cameras.csv'), encoding='utf-8')))
    out = []
    for c in cams:
        d = query(Q.format(lat=c['lat'], lon=c['lon']))
        roads = [e['tags'] for e in d['elements'] if e.get('type') == 'way']
        cnt = [e for e in d['elements'] if e.get('type') == 'count']
        best = min(roads, key=lambda t: RANK.index(t['highway']) if t.get('highway') in RANK else 99) if roads else {}
        out.append({'cam': c['cam'], 'road_name': best.get('name', ''), 'highway': best.get('highway', ''), 'lanes': best.get('lanes', ''), 'oneway': best.get('oneway', ''), 'n_road_ways': len(roads), 'poi_300m': cnt[0]['tags']['total'] if cnt else ''})
        print(c['cam'], out[-1]['highway'], out[-1]['road_name'])
    with open(os.path.join(CLEAN, 'osm_camera_context.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
if __name__ == '__main__':
    main()

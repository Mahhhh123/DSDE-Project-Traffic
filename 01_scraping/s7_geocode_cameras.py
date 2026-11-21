import csv, json, os, urllib.parse
from common import fetch, ROOT

def main():
    imgs = csv.DictReader(open(os.path.join(ROOT, 'data', 'clean', 'images.csv'), encoding='utf-8'))
    locs = {}
    for r in imgs:
        locs.setdefault(r['cam'], r['location'])
    out = []
    for cam, loc in sorted(locs.items(), key=lambda x: int(x[0])):
        q = urllib.parse.quote(loc.replace('แยก', 'แยก ') + ' กรุงเทพมหานคร')
        res = json.loads(fetch('https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=th&viewbox=100.3,14.0,100.9,13.5&bounded=1&q=' + q, 'nominatim', delay=1.2))
        out.append({'cam': cam, 'location': loc, 'lat': res[0]['lat'] if res else '', 'lon': res[0]['lon'] if res else '', 'match': int(bool(res)), 'osm_name': res[0]['display_name'][:80] if res else ''})
        print(cam, loc, out[-1]['match'])
    with open(os.path.join(ROOT, 'data', 'cameras_geocoded.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print('matched', sum((o['match'] for o in out)), '/', len(out))
if __name__ == '__main__':
    main()

import csv, json, os
from common import fetch, CLEAN, ROOT, START, END
POINTS = {'center': (13.7563, 100.5018), 'north': (13.86, 100.56), 'south': (13.68, 100.55), 'east': (13.75, 100.7), 'west': (13.73, 100.42)}
VARS = 'precipitation,rain,cloud_cover,temperature_2m,relative_humidity_2m'

def load_points():
    p = os.path.join(ROOT, 'data', 'cameras.csv')
    if os.path.exists(p):
        return {r['cam']: (float(r['lat']), float(r['lon'])) for r in csv.DictReader(open(p, encoding='utf-8'))}
    return POINTS

def main():
    pts = load_points()
    keys = list(pts)
    out = []
    for i in range(0, len(keys), 20):
        ks = keys[i:i + 20]
        url = 'https://archive-api.open-meteo.com/v1/archive?latitude=%s&longitude=%s&start_date=%s&end_date=%s&hourly=%s&timezone=Asia%%2FBangkok' % (','.join((str(pts[k][0]) for k in ks)), ','.join((str(pts[k][1]) for k in ks)), START, END, VARS)
        d = json.loads(fetch(url, 'open_meteo'))
        d = d if isinstance(d, list) else [d]
        for k, loc in zip(ks, d):
            h = loc['hourly']
            for j, t in enumerate(h['time']):
                out.append({'point': k, 'time': t.replace('T', ' '), **{v: h[v][j] for v in VARS.split(',')}})
    with open(os.path.join(CLEAN, 'openmeteo_hourly.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print('rows', len(out), 'points', len(keys))
if __name__ == '__main__':
    main()

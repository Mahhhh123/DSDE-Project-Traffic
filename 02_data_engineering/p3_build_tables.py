import csv, os, json, math, statistics as st, collections, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = lambda n: os.path.join(ROOT, 'data', 'clean', n)
rd = lambda n: list(csv.DictReader(open(C(n), encoding='utf-8')))

def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    return 6371 * 2 * math.asin(math.sqrt(math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2))

def level(mm):
    return 'dry' if mm < 0.5 else 'light' if mm < 5 else 'heavy'

def main():
    imgs = rd('images.csv')
    det = {r['image_id']: r for r in rd('detections.csv')}
    rain = rd('bma_rain_hourly.csv')
    stations = {r['station']: (float(r['lat']), float(r['lon'])) for r in rd('bma_rain_stations.csv')}
    N_ST = len(stations)
    by_slot = collections.defaultdict(dict)
    for r in rain:
        by_slot[r['query_time']][r['station']] = float(r['rf1h'] or 0)

    def city(date, h):
        q = '%s %02d:00' % (date, h + 1)
        v = by_slot.get(q)
        if v is None:
            return None
        vals = list(v.values()) + [0.0] * (N_ST - len(v))
        return {'mean': sum(vals) / len(vals), 'max': max(vals), 'p75': sorted(vals)[int(0.75 * len(vals))], 'share1': sum((x >= 1 for x in vals)) / len(vals)}
    cams = {}
    if os.path.exists(os.path.join(ROOT, 'data', 'cameras.csv')):
        cams = {r['cam']: (float(r['lat']), float(r['lon'])) for r in csv.DictReader(open(os.path.join(ROOT, 'data', 'cameras.csv'), encoding='utf-8'))}
    near = {c: min(stations, key=lambda s: hav(p, stations[s])) for c, p in cams.items()}
    fact = []
    for r in imgs:
        if r['is_broken'] == '1' or r['image_id'] not in det:
            continue
        h = int(r['hour'])
        cr = city(r['date'], h)
        if cr is None:
            continue
        if r['cam'] in near:
            mm = by_slot['%s %02d:00' % (r['date'], h + 1)].get(near[r['cam']], 0.0)
            lv = level(mm)
            src = 'station'
        else:
            mm = cr['mean']
            lv = 'heavy' if cr['share1'] >= 0.25 else 'light' if cr['share1'] >= 0.05 else 'dry'
            src = 'city'
        d = det[r['image_id']]
        fact.append({**{k: r[k] for k in ('image_id', 'cam', 'location', 'ts', 'date', 'hour', 'period', 'day_type')}, 'rain_mm': round(mm, 2), 'rain_level': lv, 'rain_source': src, 'city_rain_mean': round(cr['mean'], 2), 'city_rain_share': round(cr['share1'], 3), 'vehicles': int(d['vehicles']), 'car': int(d['car']), 'motorcycle': int(d['motorcycle']), 'bus': int(d['bus']), 'truck': int(d['truck']), 'occupancy': float(d['occupancy']), 'brightness': float(d['brightness'])})
    base = collections.defaultdict(list)
    for f in fact:
        if f['rain_level'] == 'dry':
            base[f['cam'], f['hour'], f['day_type']].append(f['vehicles'])
    camall = collections.defaultdict(list)
    for f in fact:
        camall[f['cam']].append(f['vehicles'])
    for f in fact:
        b = base.get((f['cam'], f['hour'], f['day_type']))
        ok = bool(b) and len(b) >= 3
        m = st.median(b) if ok else st.median(camall[f['cam']])
        f['baseline'] = m
        f['baseline_matched'] = int(ok)
        f['cong_index'] = round((f['vehicles'] + 1) / (m + 1), 3)
    with open(C('fact_images.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.DictWriter(fh, fieldnames=list(fact[0]))
        w.writeheader()
        w.writerows(fact)
    print('fact rows', len(fact))
if __name__ == '__main__':
    main()

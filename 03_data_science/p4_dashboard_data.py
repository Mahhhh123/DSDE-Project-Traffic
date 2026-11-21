import csv, os, json, random, math, statistics as st, collections, re
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
C = lambda n: os.path.join(ROOT, 'data', 'clean', n)
PER = ['เช้า', 'สาย', 'บ่าย', 'เย็น', 'ค่ำ']
LV = ['dry', 'light', 'heavy']
DT = ['วันธรรมดา', 'วันหยุด']
random.seed(7)

def gmean(v):
    return math.exp(st.mean((math.log(x) for x in v)))

def boot(groups, reps=1000):
    groups = {c: [math.log(x) for x in g] for c, g in groups.items()}
    cams = list(groups)
    allv = [v for g in groups.values() for v in g]
    if len(cams) < 3:
        return [round(math.exp(st.mean(allv)), 3), None, None]
    sums = {c: (sum(g), len(g)) for c, g in groups.items()}
    res = []
    for _ in range(reps):
        s = n = 0
        for c in random.choices(cams, k=len(cams)):
            s += sums[c][0]
            n += sums[c][1]
        res.append(s / n)
    res.sort()
    return [round(math.exp(st.mean(allv)), 3), round(math.exp(res[int(0.025 * reps)]), 3), round(math.exp(res[int(0.975 * reps)]), 3)]

def main():
    F = list(csv.DictReader(open(C('fact_images.csv'), encoding='utf-8')))
    for f in F:
        for k in ('hour', 'vehicles', 'car', 'motorcycle', 'bus', 'truck', 'baseline_matched'):
            f[k] = int(f[k])
        for k in ('rain_mm', 'cong_index', 'occupancy', 'brightness', 'city_rain_share'):
            f[k] = float(f[k])
    imgs = list(csv.DictReader(open(C('images.csv'), encoding='utf-8')))
    rain = list(csv.DictReader(open(C('bma_rain_hourly.csv'), encoding='utf-8')))
    nst = sum((1 for _ in open(C('bma_rain_stations.csv'), encoding='utf-8'))) - 1
    dates = sorted({i['date'] for i in imgs})
    hours = list(range(6, 22))
    dtype = {r['date']: r['day_type'] for r in csv.DictReader(open(C('day_type.csv'), encoding='utf-8'))}
    slot = collections.defaultdict(list)
    for r in rain:
        slot[r['query_time']].append(float(r['rf1h'] or 0))
    cov = collections.Counter(((i['date'], int(i['hour'])) for i in imgs if i['is_broken'] == '0'))
    grid = []
    for d in dates:
        for h in hours:
            v = slot.get('%s %02d:00' % (d, h + 1))
            vals = (v or []) + [0.0] * (nst - len(v or []))
            grid.append({'d': d, 'h': h, 'share': round(sum((x >= 1 for x in vals)) / nst, 3) if v else None, 'max': max(vals) if v else None, 'img': cov.get((d, h), 0)})
    hourly = {}
    for dt in DT:
        for lv in ('dry', 'rain'):
            row = []
            for h in hours:
                g = [f['vehicles'] for f in F if f['day_type'] == dt and f['hour'] == h and ((f['rain_level'] == 'dry') == (lv == 'dry'))]
                row.append([round(st.mean(g), 2), len(g)] if g else [None, 0])
            hourly['%s|%s' % (dt, lv)] = row
    eff = []
    for dt in DT + ['ทั้งหมด']:
        for p in PER + ['ทั้งวัน']:
            for lv in LV:
                sel = [f for f in F if f['baseline_matched'] and f['rain_level'] == lv and (dt == 'ทั้งหมด' or f['day_type'] == dt) and (p == 'ทั้งวัน' or f['period'] == p)]
                if not sel:
                    eff.append({'dt': dt, 'p': p, 'lv': lv, 'n': 0, 'cams': 0})
                    continue
                g = collections.defaultdict(list)
                m = collections.defaultdict(list)
                for f in sel:
                    g[f['cam']].append(f['cong_index'])
                    m[f['cam']].append(f['motorcycle'] / f['vehicles'] if f['vehicles'] else 0)
                mean, lo, hi = boot(g)
                eff.append({'dt': dt, 'p': p, 'lv': lv, 'n': len(sel), 'cams': len(g), 'idx': mean, 'lo': lo, 'hi': hi, 'moto': round(st.mean((v for vs in m.values() for v in vs)), 3)})
    cams = {}
    for f in F:
        cams.setdefault(f['cam'], {'loc': f['location'], 'rows': []})['rows'].append(f)
    geo = {}
    gp = os.path.join(ROOT, 'data', 'cameras.csv')
    if os.path.exists(gp):
        geo = {r['cam']: r for r in csv.DictReader(open(gp, encoding='utf-8'))}
    stations = [[float(r['lon']), float(r['lat']), r['name']] for r in csv.DictReader(open(C('bma_rain_stations.csv'), encoding='utf-8'))]
    camlist, series = ([], {})
    for c, o in cams.items():
        rows = o['rows']
        dry = [r['cong_index'] for r in rows if r['baseline_matched'] and r['rain_level'] == 'dry']
        wet = [r['cong_index'] for r in rows if r['baseline_matched'] and r['rain_level'] != 'dry']
        camlist.append({'cam': int(c), 'loc': o['loc'], 'n': len(rows), 'mean_veh': round(st.mean((r['vehicles'] for r in rows)), 1), 'dry': round(gmean(dry), 3) if dry else None, 'wet': round(gmean(wet), 3) if len(wet) >= 6 else None, 'n_wet': len(wet), 'lat': float(geo[c]['lat']) if c in geo else None, 'lon': float(geo[c]['lon']) if c in geo else None, 'detail': geo[c]['detail_th'] if c in geo else ''})
        agg = collections.defaultdict(list)
        for r in rows:
            agg[r['date'], r['hour']].append(r['vehicles'])
        series[c] = [[d, h, round(st.mean(agg[d, h]), 1) if agg.get((d, h)) else None] for d in dates for h in hours]
    broken = sum((i['is_broken'] == '1' for i in imgs))
    out = {'meta': {'images': len(imgs), 'valid': len(imgs) - broken, 'broken': broken, 'used': len(F), 'cams': len(cams), 'dates': dates, 'day_type': dtype, 'stations': nst, 'rain_source': F[0]['rain_source'], 'rain_hours': sum((1 for g in grid if g['share'] and g['share'] >= 0.05))}, 'grid': grid, 'hours': hours, 'stations': stations, 'hourly': hourly, 'effect': eff, 'cams': sorted(camlist, key=lambda x: x['cam']), 'series': series}
    js = json.dumps(out, ensure_ascii=False, separators=(',', ':'))
    open(C('dashboard.json'), 'w', encoding='utf-8').write(js)
    page = os.path.join(ROOT, '04_dashboard', 'dashboard.html')
    if os.path.exists(page):
        s = open(page, encoding='utf-8').read()
        s = re.sub('(<script id="data" type="application/json">)[\\s\\S]*?(</script>)', lambda m: m.group(1) + js.replace('</', '<\\/') + m.group(2), s)
        open(page, 'w', encoding='utf-8').write(s)
        print('embedded into', os.path.basename(page))
    print('dashboard.json', len(js) // 1024, 'KB')
if __name__ == '__main__':
    main()

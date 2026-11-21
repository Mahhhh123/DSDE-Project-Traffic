import csv, os, sys, random, zipfile, collections, statistics as st
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'label_sample')
C = lambda n: os.path.join(ROOT, 'data', 'clean', n)

def sample(zp, n=200):
    random.seed(42)
    F = list(csv.DictReader(open(C('fact_images.csv'), encoding='utf-8')))
    paths = {r['image_id']: r['path'] for r in csv.DictReader(open(C('images.csv'), encoding='utf-8'))}
    strata = collections.defaultdict(list)
    for f in F:
        strata[f['period'], f['rain_level'] != 'dry'].append(f)
    per = max(1, n // len(strata))
    pick = []
    for k, rows in sorted(strata.items()):
        random.shuffle(rows)
        pick += rows[:per]
    os.makedirs(OUT, exist_ok=True)
    zf = zipfile.ZipFile(zp)
    raw = {}
    for i in zf.infolist():
        nm = i.filename
        if not i.flag_bits & 2048:
            try:
                nm = nm.encode('cp437').decode('utf-8')
            except Exception:
                pass
        raw[nm] = i.filename
    with open(os.path.join(OUT, 'labels.csv'), 'w', newline='', encoding='utf-8') as fh:
        w = csv.writer(fh)
        w.writerow(['file', 'image_id', 'period', 'rain_level', 'yolo_count', 'human_count'])
        for f in pick:
            fn = f['image_id'] + '.jpg'
            open(os.path.join(OUT, fn), 'wb').write(zf.read(raw[paths[f['image_id']]]))
            w.writerow([fn, f['image_id'], f['period'], f['rain_level'], f['vehicles'], ''])
    print('sampled', len(pick), '→', OUT)

def score():
    rows = [r for r in csv.DictReader(open(os.path.join(OUT, 'labels.csv'), encoding='utf-8')) if r['human_count'].strip()]
    g = collections.defaultdict(list)
    for r in rows:
        e = int(r['yolo_count']) - int(r['human_count'])
        g['ทั้งหมด'].append(e)
        g[r['period']].append(e)
        g['ฝน' if r['rain_level'] != 'dry' else 'ไม่ฝน'].append(e)
    for k, es in g.items():
        print('%-8s n=%3d  MAE %.2f  bias %+.2f (บวก=YOLO นับเกิน)' % (k, len(es), st.mean((abs(e) for e in es)), st.mean(es)))
if __name__ == '__main__':
    score() if '--score' in sys.argv else sample(sys.argv[1])

import zipfile, re, csv, os, sys, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAT = re.compile('(?:^|/)(\\d+)/(\\d+)_(.+?)_(\\d{8})_(\\d{6})\\.jpe?g$', re.I)
BROKEN_BYTES = 3000

def period(h):
    return 'เช้า' if h < 9 else 'สาย' if h < 12 else 'บ่าย' if h < 16 else 'เย็น' if h < 19 else 'ค่ำ'

def day_types():
    p = os.path.join(ROOT, 'data', 'clean', 'day_type.csv')
    return {r['date']: r['day_type'] for r in csv.DictReader(open(p, encoding='utf-8'))} if os.path.exists(p) else {}

def names(src):
    if src.endswith('.zip'):
        for i in zipfile.ZipFile(src).infolist():
            n = i.filename
            if not i.flag_bits & 2048:
                try:
                    n = n.encode('cp437').decode('utf-8')
                except Exception:
                    pass
            yield (n, i.file_size)
    else:
        for dp, _, fs in os.walk(src):
            for f in fs:
                yield (os.path.join(dp, f), os.path.getsize(os.path.join(dp, f)))

def main(src):
    dt = day_types()
    out = []
    bad = 0
    for n, size in names(src):
        m = PAT.search(n)
        if not m:
            bad += n.lower().endswith('.jpg')
            continue
        cam, _, loc, d, t = m.groups()
        ts = datetime.datetime.strptime(d + t, '%Y%m%d%H%M%S')
        date = ts.date().isoformat()
        out.append({'image_id': '%s_%s' % (cam, ts.strftime('%Y%m%d%H%M%S')), 'cam': int(cam), 'location': loc.split('_')[0], 'ts': ts.isoformat(sep=' '), 'date': date, 'hour': ts.hour, 'period': period(ts.hour), 'day_type': dt.get(date, 'วันหยุด' if ts.weekday() >= 5 else 'วันธรรมดา'), 'size': size, 'is_broken': int(size < BROKEN_BYTES), 'path': n})
    out.sort(key=lambda r: (r['cam'], r['ts']))
    with open(os.path.join(ROOT, 'data', 'clean', 'images.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print('images', len(out), 'cams', len({r['cam'] for r in out}), 'broken', sum((r['is_broken'] for r in out)), 'unparsed', bad)
if __name__ == '__main__':
    main(sys.argv[1])

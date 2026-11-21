import os, time, json, urllib.request, urllib.parse, datetime
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'data', 'raw')
CLEAN = os.path.join(ROOT, 'data', 'clean')
os.makedirs(RAW, exist_ok=True)
os.makedirs(CLEAN, exist_ok=True)
UA = 'Mozilla/5.0 (DSDE-CEDT student project; contact via course)'
START, END = (datetime.date(2026, 8, 25), datetime.date(2026, 8, 31))
BKK = (13.7563, 100.5018)

def log(source, url, status, nbytes):
    with open(os.path.join(RAW, 'scrape_log.csv'), 'a', encoding='utf-8') as f:
        f.write('%s,%s,%s,%s,"%s"\n' % (datetime.datetime.now().isoformat(timespec='seconds'), source, status, nbytes, url))

def fetch(url, source, data=None, delay=1.0, tries=3, cookie=None, headers=None):
    body = urllib.parse.urlencode(data).encode() if isinstance(data, dict) else data
    for k in range(tries):
        time.sleep(delay * (k + 1))
        try:
            req = urllib.request.Request(url, data=body, headers={'User-Agent': UA, 'Accept': '*/*', **(headers or {})})
            opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie)) if cookie is not None else urllib.request.build_opener()
            with opener.open(req, timeout=90) as r:
                raw = r.read()
                log(source, url, r.status, len(raw))
                return raw.decode('utf-8', 'replace')
        except Exception as e:
            log(source, url, 'ERR ' + type(e).__name__, 0)
            if k == tries - 1:
                raise

def days():
    d = START
    while d <= END:
        yield d
        d += datetime.timedelta(days=1)

def save_json(name, obj):
    with open(os.path.join(RAW, name), 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)

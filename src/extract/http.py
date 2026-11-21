import csv
import datetime
import os
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

from src.common.config import CFG, path

S = CFG['scrape']
_robots = {}


def allowed(url):
    p = urlparse(url)
    base = '%s://%s' % (p.scheme, p.netloc)
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = requests.get(base + '/robots.txt', headers={'User-Agent': S['user_agent']}, timeout=15)
            rp.parse(r.text.splitlines() if r.status_code == 200 else [])
        except requests.RequestException:
            rp.parse([])
        _robots[base] = rp
    return _robots[base].can_fetch(S['user_agent'], url)


def manifest(source, url, status, nbytes, file):
    p = path('landing', '_manifest.csv')
    new = not os.path.exists(p)
    with open(p, 'a', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['fetched_at', 'source', 'status', 'bytes', 'file', 'url'])
        w.writerow([datetime.datetime.now().isoformat(timespec='seconds'), source, status, nbytes, file, url])


def fetch(url, source, file, data=None, session=None, delay=None, check_robots=True):
    out = path('landing', source, file)
    if os.path.exists(out) and os.path.getsize(out) > 0:
        return open(out, 'rb').read()
    if check_robots and not allowed(url):
        manifest(source, url, 'BLOCKED_BY_ROBOTS', 0, file)
        raise PermissionError('robots.txt disallows ' + url)
    sess = session or requests
    for k in range(S['retries']):
        time.sleep((delay if delay is not None else S['delay_seconds']) * (k + 1))
        try:
            r = (sess.post(url, data=data, headers={'User-Agent': S['user_agent']}, timeout=S['timeout_seconds']) if data is not None
                 else sess.get(url, headers={'User-Agent': S['user_agent']}, timeout=S['timeout_seconds']))
            r.raise_for_status()
            with open(out, 'wb') as f:
                f.write(r.content)
            manifest(source, url, r.status_code, len(r.content), file)
            return r.content
        except requests.RequestException as e:
            manifest(source, url, 'ERR ' + type(e).__name__, 0, file)
            if k == S['retries'] - 1:
                raise

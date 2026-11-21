import csv
import datetime
import http.cookiejar
import json
import os
import re
import sys

from common import CLEAN, days, fetch

URL = 'https://weather.bangkok.go.th/Flood/Graph/AllStation'


def cell(c):
    return re.sub(r'<[^>]+>|\s+', ' ', c).strip()


def be_to_iso(s):
    d, t = s.split()
    dd, mm, yy = d.split('/')
    return '%04d-%s-%s %s' % (int(yy) - 543, mm, dd, t)


def parse(html):
    rows = []
    table = re.search(r'<table[\s\S]*?</table>', html)
    for r in re.findall(r'<tr[\s\S]*?</tr>', table.group(0) if table else '')[1:]:
        c = [cell(x) for x in re.findall(r'<td[\s\S]*?</td>', r)]
        if len(c) >= 5 and c[0].startswith('FL.'):
            rows.append(c)
    stations = []
    i = html.find('"flood_code"')
    if i > 0:
        stations, _ = json.JSONDecoder().raw_decode(html[html.rfind('[', 0, i):])
    return rows, stations


def main(test=False):
    jar = http.cookiejar.CookieJar()
    fetch(URL, 'bma_road_flood', cookie=jar)
    slots = [(datetime.date(2026, 8, 29), 16)] if test else [(d, h) for d in days() for h in range(6, 21)]
    out, meta = [], {}
    for d, h in slots:
        ds, ts = d.strftime('%d/%m/%Y'), '%02d:30' % h
        html = fetch(URL, 'bma_road_flood', data={'datePick': ds, 'StationTime': ts}, cookie=jar, delay=1.5)
        rows, stations = parse(html)
        for s in stations:
            meta[s['flood_code']] = s
        for c in rows:
            level = float(c[4]) if re.fullmatch(r'-?\d+(\.\d+)?', c[4]) else None
            out.append({'sensor': c[0], 'road': c[1], 'name': c[2], 'time': be_to_iso(c[3]), 'query_time': '%s %s' % (d.isoformat(), ts), 'flood_cm': level})
        print(d, ts, 'sensors', len(rows), 'flooded', sum(1 for c in rows if re.fullmatch(r'\d+(\.\d+)?', c[4]) and float(c[4]) > 0))
    suffix = '_test' if test else ''
    with open(os.path.join(CLEAN, 'bma_road_flood_hourly%s.csv' % suffix), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['sensor', 'road', 'name', 'time', 'query_time', 'flood_cm'])
        w.writeheader()
        w.writerows(out)
    with open(os.path.join(CLEAN, 'bma_road_flood_sensors%s.csv' % suffix), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['sensor', 'name', 'road', 'system', 'lat', 'lon'])
        for s in meta.values():
            w.writerow([s['flood_code'], s['flood_name'], s['road_name'], s.get('flood_system_id'), s['latitude'], s['longitude']])
    print('rows', len(out), 'sensors', len(meta))


if __name__ == '__main__':
    main('--test' in sys.argv)

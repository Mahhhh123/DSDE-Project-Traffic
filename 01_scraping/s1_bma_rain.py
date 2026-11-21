import re, json, csv, os, sys, http.cookiejar, datetime
from common import fetch, days, CLEAN, RAW, save_json
URL = 'https://weather.bangkok.go.th/rain/RainHistory/IndexAllStation'
cell = lambda c: re.sub('<[^>]+>|\\s+', ' ', c).strip()

def parse(html):
    tb = re.search('<table[\\s\\S]*?</table>', html)
    rows = re.findall('<tr[\\s\\S]*?</tr>', tb.group(0)) if tb else []
    out = []
    for r in rows[1:]:
        c = [cell(x) for x in re.findall('<td[\\s\\S]*?</td>', r)]
        if len(c) >= 12:
            out.append(c[:12])
    m = re.search('var datawater = (\\[.*?\\]);', html, re.S)
    return (out, json.loads(m.group(1)) if m else [])

def be_to_iso(s):
    d, t = s.split()
    dd, mm, yy = d.split('/')
    return '%04d-%s-%s %s' % (int(yy) - 543, mm, dd, t)

def main(test=False):
    jar = http.cookiejar.CookieJar()
    fetch(URL, 'bma_rain', cookie=jar)
    slots = [(datetime.date(2026, 8, 31), 17)] if test else [(d, h) for d in days() for h in range(6, 22)]
    rows, stations = ([], {})
    for d, h in slots:
        ds, ts = (d.strftime('%d/%m/%Y'), '%02d:00' % h)
        html = fetch(URL, 'bma_rain', data={'datePick': ds, 'StationTime': ts, 'datePick_Stop': ds, 'StationTime_Stop': ts, 'account': '4'}, cookie=jar, delay=1.5)
        tab, meta = parse(html)
        for s in meta:
            stations[s['rain_code']] = s
        for c in tab:
            rows.append({'station': c[0], 'district': c[1], 'name': c[2], 'time': be_to_iso(c[3]), 'query_time': '%s %s' % (d.isoformat(), ts), 'rf15': c[5], 'rf1h': c[7], 'rf3h': c[8], 'rf24h': c[11]})
        print(d, ts, 'stations', len(tab))
    with open(os.path.join(CLEAN, 'bma_rain_hourly_test.csv' if test else 'bma_rain_hourly.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(CLEAN, 'bma_rain_stations_test.csv' if test else 'bma_rain_stations.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['station', 'name', 'district', 'district_en', 'lat', 'lon'])
        for s in stations.values():
            w.writerow([s['rain_code'], s['rain_shortname'], s['district_name'], s['district_name_en'], s['latitude'], s['longitude']])
    print('rows', len(rows), 'stations meta', len(stations))
if __name__ == '__main__':
    main('--test' in sys.argv)

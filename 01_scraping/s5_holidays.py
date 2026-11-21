import csv, os, re, datetime, html as H
from common import fetch, CLEAN, days
MON = {m: i + 1 for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'])}

def main():
    html = fetch('https://www.timeanddate.com/holidays/thailand/2026?hol=1&lang=en', 'timeanddate', headers={'Accept-Language': 'en'})
    hol = []
    for tr in re.findall('<tr[^>]*data-date="?(\\d+)"?[^>]*>([\\s\\S]*?)</tr>', html):
        ms, body = tr
        cells = [re.sub('<[^>]+>', ' ', c).strip() for c in re.findall('<t[hd][^>]*>([\\s\\S]*?)</t[hd]>', body)]
        d = datetime.datetime.fromtimestamp(int(ms) / 1000, datetime.timezone.utc).date()
        name = cells[2] if len(cells) > 2 else ''
        kind = cells[3] if len(cells) > 3 else ''
        hol.append({'date': d.isoformat(), 'name': H.unescape(re.sub('\\s+', ' ', name)), 'type': re.sub('\\s+', ' ', kind)})
    with open(os.path.join(CLEAN, 'holidays_2026.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=['date', 'name', 'type'])
        w.writeheader()
        w.writerows(hol)
    public = {h['date']: h['name'] for h in hol if 'Public' in h['type'] or 'Bank' in h['type'] or 'National' in h['type']}
    with open(os.path.join(CLEAN, 'day_type.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['date', 'weekday', 'day_type', 'holiday'])
        for d in days():
            wd = d.strftime('%a')
            h = public.get(d.isoformat(), '')
            w.writerow([d, wd, 'วันหยุด' if d.weekday() >= 5 or h else 'วันธรรมดา', h])
    print('holidays', len(hol), '· public in range:', [public.get(d.isoformat()) for d in days() if public.get(d.isoformat())])
if __name__ == '__main__':
    main()

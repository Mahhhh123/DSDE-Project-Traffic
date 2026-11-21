import csv, json, os, datetime
from common import fetch, CLEAN, days, BKK

def local(s):
    return (datetime.datetime.fromisoformat(s) + datetime.timedelta(hours=7)).strftime('%H:%M')

def main():
    out = []
    for d in days():
        r = json.loads(fetch('https://api.sunrise-sunset.org/json?lat=%s&lng=%s&date=%s&formatted=0' % (BKK[0], BKK[1], d), 'sunrise_sunset'))['results']
        out.append({'date': d.isoformat(), 'civil_dawn': local(r['civil_twilight_begin']), 'sunrise': local(r['sunrise']), 'sunset': local(r['sunset']), 'civil_dusk': local(r['civil_twilight_end'])})
    with open(os.path.join(CLEAN, 'sun_daily.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    print(out[0], out[-1])
if __name__ == '__main__':
    main()

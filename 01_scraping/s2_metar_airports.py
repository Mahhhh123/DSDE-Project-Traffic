import csv, io, os
from common import fetch, CLEAN, START, END
URL = 'https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=VTBD&station=VTBS&data=tmpc&data=relh&data=p01m&data=wxcodes&data=vsby&data=skyc1&year1={a.year}&month1={a.month}&day1={a.day}&year2={b.year}&month2={b.month}&day2={b.day}&tz=Asia%2FBangkok&format=onlycomma&latlon=yes&missing=M&trace=T&direct=no&report_type=3&report_type=4'

def rain_level(wx):
    wx = wx or ''
    if 'TS' in wx and 'RA' in wx:
        return 3
    if '+RA' in wx:
        return 3
    if 'RA' in wx and (not wx.strip().startswith('-')) and ('-RA' not in wx):
        return 2
    if 'RA' in wx or 'DZ' in wx or 'SH' in wx:
        return 1
    return 0

def main():
    import datetime
    txt = fetch(URL.format(a=START, b=END + datetime.timedelta(days=1)), 'iem_metar')
    rows = list(csv.DictReader(io.StringIO(txt)))
    for r in rows:
        r['wxcodes'] = '' if r['wxcodes'] == 'M' else r['wxcodes']
        r['rain_level'] = rain_level(r['wxcodes'])
    with open(os.path.join(CLEAN, 'metar_30min.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print('rows', len(rows), 'with rain', sum((r['rain_level'] > 0 for r in rows)))
if __name__ == '__main__':
    main()

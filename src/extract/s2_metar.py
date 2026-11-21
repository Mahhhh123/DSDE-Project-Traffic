import datetime

from src.common.config import CFG
from src.extract.http import fetch

URL = ('https://mesonet.agron.iastate.edu/cgi-bin/request/asos.py?station=VTBD&station=VTBS&data=tmpc&data=relh&data=p01m'
       '&data=wxcodes&data=vsby&data=skyc1&year1={a.year}&month1={a.month}&day1={a.day}&year2={b.year}&month2={b.month}&day2={b.day}'
       '&tz=Asia%2FBangkok&format=onlycomma&latlon=yes&missing=M&trace=T&direct=no&report_type=3&report_type=4')


def main():
    a = datetime.date.fromisoformat(str(CFG['period']['start']))
    b = datetime.date.fromisoformat(str(CFG['period']['end'])) + datetime.timedelta(days=1)
    raw = fetch(URL.format(a=a, b=b), 'metar', 'metar_vtbd_vtbs.csv', check_robots=False)
    print('metar bytes', len(raw))


if __name__ == '__main__':
    main()

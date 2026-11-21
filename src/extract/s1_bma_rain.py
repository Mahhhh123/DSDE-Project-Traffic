import requests

from src.common.config import days
from src.extract.http import fetch

URL = 'https://weather.bangkok.go.th/rain/RainHistory/IndexAllStation'


def main():
    sess = requests.Session()
    sess.get(URL, timeout=60)
    n = 0
    for d in days():
        for h in range(6, 22):
            ds, ts = d.strftime('%d/%m/%Y'), '%02d:00' % h
            fetch(URL, 'bma_rain', 'rain_%s_%02d.html' % (d.isoformat(), h), session=sess,
                  data={'datePick': ds, 'StationTime': ts, 'datePick_Stop': ds, 'StationTime_Stop': ts, 'account': '4'})
            n += 1
    print('bma_rain pages', n)


if __name__ == '__main__':
    main()

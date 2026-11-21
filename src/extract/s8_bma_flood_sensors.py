import requests

from src.common.config import days
from src.extract.http import fetch

URL = 'https://weather.bangkok.go.th/Flood/Graph/AllStation'


def main():
    sess = requests.Session()
    sess.get(URL, timeout=60)
    n = 0
    for d in days():
        for h in range(6, 21):
            fetch(URL, 'bma_flood', 'flood_%s_%02d30.html' % (d.isoformat(), h), session=sess,
                  data={'datePick': d.strftime('%d/%m/%Y'), 'StationTime': '%02d:30' % h})
            n += 1
    print('bma_flood pages', n)


if __name__ == '__main__':
    main()

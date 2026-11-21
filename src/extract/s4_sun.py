from src.common.config import days
from src.extract.http import fetch

LAT, LON = 13.7563, 100.5018


def main():
    for d in days():
        fetch('https://api.sunrise-sunset.org/json?lat=%s&lng=%s&date=%s&formatted=0' % (LAT, LON, d), 'sun', 'sun_%s.json' % d, check_robots=False)
    print('sun days done')


if __name__ == '__main__':
    main()

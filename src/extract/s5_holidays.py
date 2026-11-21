from src.extract.http import fetch


def main():
    raw = fetch('https://www.timeanddate.com/holidays/thailand/2026?hol=1', 'holidays', 'thailand_2026.html')
    print('holidays bytes', len(raw))


if __name__ == '__main__':
    main()

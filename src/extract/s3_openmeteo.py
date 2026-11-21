import csv

from src.common.config import CFG, path
from src.extract.http import fetch

VARS = 'precipitation,rain,cloud_cover,temperature_2m,relative_humidity_2m'


def cameras():
    rows = csv.DictReader(open(path('cctv_info'), encoding='utf-8-sig'))
    return [(r['camera_id'], r['latitude'], r['longitude']) for r in rows if r['latitude'] and r['longitude']]


def main():
    cams = cameras()
    for i in range(0, len(cams), 20):
        part = cams[i:i + 20]
        url = ('https://archive-api.open-meteo.com/v1/archive?latitude=%s&longitude=%s&start_date=%s&end_date=%s&hourly=%s&timezone=Asia%%2FBangkok'
               % (','.join(c[1] for c in part), ','.join(c[2] for c in part), CFG['period']['start'], CFG['period']['end'], VARS))
        fetch(url, 'openmeteo', 'batch_%02d_cams_%s.json' % (i // 20, '-'.join(c[0] for c in part)), check_robots=False)
    print('openmeteo cameras', len(cams))


if __name__ == '__main__':
    main()

import csv, os
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BAD_EN = {'connect BMAcctv', '0', ''}

def main():
    rows = list(csv.DictReader(open(os.path.join(ROOT, 'data', 'cctv_info.csv'), encoding='utf-8-sig')))
    with open(os.path.join(ROOT, 'data', 'cameras.csv'), 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['cam', 'lat', 'lon', 'name_th', 'name_en', 'detail_th'])
        for r in sorted(rows, key=lambda r: int(r['camera_id'])):
            en = '' if r['location_en'] in BAD_EN else r['location_en']
            w.writerow([r['camera_id'], r['latitude'], r['longitude'], r['location'], en, r['location_detail']])
    print('cameras', len(rows), 'missing english name', sum((r['location_en'] in BAD_EN for r in rows)))
if __name__ == '__main__':
    main()

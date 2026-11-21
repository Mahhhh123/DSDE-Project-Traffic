import datetime
import glob
import io
import json
import os
import re
import zipfile

import pandas as pd
from bs4 import BeautifulSoup

from src.common.config import path

PRIVATE = {'ip_address'}
NOW = datetime.datetime.now().isoformat(timespec='seconds')


def save(df, name):
    df = df.astype('string')
    df['_ingested_at'] = NOW
    out = path('bronze', name + '.parquet')
    df.to_parquet(out, index=False)
    print('bronze/%s rows=%d cols=%d' % (name, len(df), df.shape[1]))
    return df


def files(source, pattern='*'):
    return sorted(glob.glob(os.path.join(path('landing', source), pattern)))


def html_rows(html, min_cells):
    soup = BeautifulSoup(html, 'html.parser')
    table = soup.find('table')
    if table is None:
        return [], []
    header = [th.get_text(' ', strip=True) for th in table.find_all('th')]
    rows = []
    for tr in table.find_all('tr'):
        cells = [td.get_text(' ', strip=True) for td in tr.find_all('td')]
        if len(cells) >= min_cells:
            rows.append(cells)
    return header, rows


def js_array(html, marker):
    i = html.find(marker)
    if i < 0:
        return []
    arr, _ = json.JSONDecoder().raw_decode(html[html.rfind('[', 0, i):])
    return arr


def images_index():
    zf = zipfile.ZipFile(path('images_zip'))
    rows = []
    for i in zf.infolist():
        if i.is_dir():
            continue
        name = i.filename
        if not i.flag_bits & 2048:
            try:
                name = name.encode('cp437').decode('utf-8')
            except UnicodeError:
                pass
        rows.append({'path': name, 'bytes': i.file_size, 'zip_modified': '%04d-%02d-%02d %02d:%02d:%02d' % i.date_time})
    return save(pd.DataFrame(rows), 'images_index')


def cameras():
    df = pd.read_csv(path('cctv_info'), dtype=str, encoding='utf-8-sig', keep_default_na=False)
    df['_source_file'] = os.path.basename(path('cctv_info'))
    return save(df, 'cameras')


def bma_rain():
    rows, stations = [], {}
    for f in files('bma_rain', '*.html'):
        html = open(f, encoding='utf-8', errors='replace').read()
        slot = re.search(r'rain_(\d{4}-\d{2}-\d{2})_(\d{2})', f).groups()
        _, table = html_rows(html, 12)
        for c in table:
            rows.append({'query_date': slot[0], 'query_hour': slot[1], **{'c%02d' % k: v for k, v in enumerate(c[:12])}, '_source_file': os.path.basename(f)})
        m = re.search(r'var datawater = (\[.*?\]);', html, re.S)
        for s in json.loads(m.group(1)) if m else []:
            stations[s['rain_code']] = s
    save(pd.DataFrame(rows), 'bma_rain')
    save(pd.DataFrame(list(stations.values())), 'bma_rain_stations')


def metar():
    for f in files('metar', '*.csv'):
        df = pd.read_csv(f, dtype=str, keep_default_na=False)
        df['_source_file'] = os.path.basename(f)
        save(df, 'metar')


def openmeteo():
    rows = []
    for f in files('openmeteo', '*.json'):
        cams = re.search(r'_cams_([\d-]+)\.json', f).group(1).split('-')
        d = json.load(open(f))
        for cam, loc in zip(cams, d if isinstance(d, list) else [d]):
            h = loc['hourly']
            for j, t in enumerate(h['time']):
                rows.append({'cam': cam, 'time': t, **{k: h[k][j] for k in h if k != 'time'}, '_source_file': os.path.basename(f)})
    save(pd.DataFrame(rows), 'openmeteo')


def sun():
    rows = []
    for f in files('sun', '*.json'):
        r = json.load(open(f))['results']
        rows.append({'date': re.search(r'sun_(\d{4}-\d{2}-\d{2})', f).group(1), **r, '_source_file': os.path.basename(f)})
    save(pd.DataFrame(rows), 'sun')


def holidays():
    rows = []
    for f in files('holidays', '*.html'):
        soup = BeautifulSoup(open(f, encoding='utf-8', errors='replace').read(), 'html.parser')
        for tr in soup.select('table#holidays-table tbody tr[data-date]'):
            cells = [c.get_text(' ', strip=True) for c in tr.find_all(['th', 'td'])]
            rows.append({'data_date_ms': tr.get('data-date'), 'date_text': cells[0] if cells else '', 'weekday': cells[1] if len(cells) > 1 else '',
                         'name': cells[2] if len(cells) > 2 else '', 'type': cells[3] if len(cells) > 3 else '', '_source_file': os.path.basename(f)})
    save(pd.DataFrame(rows), 'holidays')


def osm():
    poi = json.load(open(path('landing', 'osm', 'poi.json')))
    save(pd.DataFrame([{'osm_type': e['type'], 'osm_id': e['id'], 'lat': e.get('lat', e.get('center', {}).get('lat')),
                        'lon': e.get('lon', e.get('center', {}).get('lon')), 'tags': json.dumps(e.get('tags', {}), ensure_ascii=False)}
                       for e in poi['elements']]), 'osm_poi')
    roads = json.load(open(path('landing', 'osm', 'major_roads.json')))
    save(pd.DataFrame([{'osm_id': w['id'], 'tags': json.dumps(w.get('tags', {}), ensure_ascii=False),
                        'geometry': json.dumps([[g['lon'], g['lat']] for g in w.get('geometry', [])])}
                       for w in roads['elements']]), 'osm_roads')


def bma_flood():
    rows, sensors = [], {}
    for f in files('bma_flood', '*.html'):
        html = open(f, encoding='utf-8', errors='replace').read()
        slot = re.search(r'flood_(\d{4}-\d{2}-\d{2})_(\d{4})', f).groups()
        _, table = html_rows(html, 5)
        for c in table:
            rows.append({'query_date': slot[0], 'query_hhmm': slot[1], **{'c%02d' % k: v for k, v in enumerate(c[:6])}, '_source_file': os.path.basename(f)})
        for s in js_array(html, '"flood_code"'):
            sensors[s['flood_code']] = {k: v for k, v in s.items() if k not in PRIVATE}
    save(pd.DataFrame(rows), 'bma_flood')
    save(pd.DataFrame(list(sensors.values())), 'bma_flood_sensors')


def bma_open_data():
    for name in ['flood_risk', 'flood_risk26', 'frd_dds']:
        raw = open(path('landing', 'bma_open_data', name + '.csv'), 'rb').read()
        for enc in ('utf-8-sig', 'cp874'):
            try:
                text = raw.decode(enc)
                break
            except UnicodeDecodeError:
                continue
        df = pd.read_csv(io.StringIO(text), dtype=str, keep_default_na=False)
        df['_encoding'] = enc
        df['_source_file'] = name + '.csv'
        save(df, 'bma_' + name)


STEPS = [images_index, cameras, bma_rain, metar, openmeteo, sun, holidays, osm, bma_flood, bma_open_data]


def main():
    for step in STEPS:
        step()


if __name__ == '__main__':
    main()

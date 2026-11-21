import base64
import io
import json
import sys
import zipfile

import numpy as np
import pandas as pd
from PIL import Image

from src.common.config import CFG, path, write_json

N = 200
CLS = ['car', 'motorcycle', 'bus', 'truck']


def sample():
    f = pd.read_parquet(path('gold', 'fact_images'), columns=['image_id', 'cam', 'ts', 'light', 'rain_level', 'is_weekend'])
    det = pd.read_parquet(path('silver', 'detections.parquet'), columns=['image_id', 'path'])
    f = f.merge(det, on='image_id')
    f['stratum'] = np.where(f['light'] == 'day', 'day', 'dark') + '_' + np.where(f['rain_level'].isin(['light', 'heavy']), 'rain', 'dry')
    quota = {'day_dry': 80, 'day_rain': 40, 'dark_dry': 40, 'dark_rain': 40}
    s = pd.concat([g.sample(min(quota[k], len(g)), random_state=CFG['model']['seed']) for k, g in f.groupby('stratum')])
    s = s.sample(frac=1, random_state=1).reset_index(drop=True)
    zf = zipfile.ZipFile(path('images_zip'))
    names = {}
    for i in zf.infolist():
        n = i.filename
        if not i.flag_bits & 2048:
            try:
                n = n.encode('cp437').decode('utf-8')
            except UnicodeError:
                pass
        names[n] = i
    items = []
    for r in s.itertuples():
        im = Image.open(io.BytesIO(zf.read(names[r.path]))).convert('RGB')
        buf = io.BytesIO()
        im.save(buf, 'JPEG', quality=85)
        items.append({'image_id': r.image_id, 'stratum': r.stratum, 'src': 'data:image/jpeg;base64,' + base64.b64encode(buf.getvalue()).decode()})
    s[['image_id', 'cam', 'ts', 'stratum']].to_csv(path('reports', 'label_sample_ids.csv'), index=False)
    page = open(path('dashboard', 'label_template.html'), encoding='utf-8').read().replace('/*__ITEMS__*/[]', json.dumps(items))
    out = path('reports', 'label_tool.html')
    open(out, 'w', encoding='utf-8').write(page)
    print('label tool:', out, 'images', len(items), s['stratum'].value_counts().to_dict())


def score(csv_path):
    lab = pd.read_csv(csv_path)
    det = pd.read_parquet(path('silver', 'detections.parquet'), columns=['image_id'] + CLS + ['vehicles'])
    ids = pd.read_csv(path('reports', 'label_sample_ids.csv'))
    m = lab.merge(det, on='image_id', suffixes=('_true', '_yolo')).merge(ids[['image_id', 'stratum']], on='image_id')
    m['vehicles_true'] = m[[c + '_true' for c in CLS]].sum(axis=1)
    m = m.rename(columns={'vehicles': 'vehicles_yolo'})
    out = {'n': int(len(m))}
    for c in CLS + ['vehicles']:
        e = m[c + '_yolo'] - m[c + '_true']
        out[c] = {'mae': round(e.abs().mean(), 3), 'bias': round(e.mean(), 3), 'true_mean': round(m[c + '_true'].mean(), 3),
                  'recall_ratio': round(m[c + '_yolo'].sum() / max(m[c + '_true'].sum(), 1), 3)}
    out['by_stratum'] = {k: {'n': int(len(g)), 'mae': round((g['vehicles_yolo'] - g['vehicles_true']).abs().mean(), 3),
                             'ratio': round(g['vehicles_yolo'].sum() / max(g['vehicles_true'].sum(), 1), 3)} for k, g in m.groupby('stratum')}
    out['spearman'] = round(m[['vehicles_true', 'vehicles_yolo']].corr('spearman').iloc[0, 1], 3)
    write_json(out, 'yolo_validation.json')
    print(json.dumps(out, indent=1))


if __name__ == '__main__':
    score(sys.argv[sys.argv.index('--score') + 1]) if '--score' in sys.argv else sample()

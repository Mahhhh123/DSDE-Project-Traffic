import glob
import io
import os
import sys
import time
import zipfile

import imagehash
import pandas as pd
from PIL import Image

from src.common.config import path

CLASSES = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
RAW_CONF = 0.10
CHUNK = 2048


def decoded(info):
    n = info.filename
    if not info.flag_bits & 2048:
        try:
            n = n.encode('cp437').decode('utf-8')
        except UnicodeError:
            pass
    return n


def main(limit=None, batch=32):
    import torch
    from ultralytics import YOLO
    dev = 'mps' if torch.backends.mps.is_available() else 'cuda' if torch.cuda.is_available() else 'cpu'
    model = YOLO(path('models', 'yolov8n.pt') if os.path.exists(path('models', 'yolov8n.pt')) else 'yolov8n.pt')
    zf = zipfile.ZipFile(path('images_zip'))
    members = sorted([i for i in zf.infolist() if i.filename.lower().endswith(('.jpg', '.jpeg'))], key=lambda i: i.filename)[:limit]
    box_dir, stat_dir = path('bronze', 'detections_raw'), path('bronze', 'image_stats')
    os.makedirs(box_dir, exist_ok=True)
    os.makedirs(stat_dir, exist_ok=True)
    t0 = time.time()
    for c in range(0, len(members), CHUNK):
        tag = 'part-%04d.parquet' % (c // CHUNK)
        if os.path.exists(os.path.join(stat_dir, tag)):
            continue
        part = members[c:c + CHUNK]
        stats, boxes = [], []
        for b in range(0, len(part), batch):
            ims, keys = [], []
            for info in part[b:b + batch]:
                name = decoded(info)
                row = {'path': name, 'bytes': info.file_size, 'decode_ok': 0, 'width': None, 'height': None, 'brightness': None, 'dhash': None}
                try:
                    im = Image.open(io.BytesIO(zf.read(info))).convert('RGB')
                    im.load()
                    g = im.convert('L').resize((64, 36))
                    row.update(decode_ok=1, width=im.width, height=im.height,
                               brightness=round(sum(g.getdata()) / (64 * 36), 2), dhash=str(imagehash.dhash(im)))
                    ims.append(im)
                    keys.append(name)
                except Exception:
                    pass
                stats.append(row)
            if not ims:
                continue
            for name, res in zip(keys, model.predict(ims, imgsz=640, conf=RAW_CONF, classes=list(CLASSES), device=dev, verbose=False)):
                for xyxy, cl, cf in zip(res.boxes.xyxy.tolist(), res.boxes.cls.tolist(), res.boxes.conf.tolist()):
                    boxes.append({'path': name, 'cls': CLASSES[int(cl)], 'conf': round(cf, 4),
                                  'x1': round(xyxy[0], 1), 'y1': round(xyxy[1], 1), 'x2': round(xyxy[2], 1), 'y2': round(xyxy[3], 1)})
        pd.DataFrame(boxes, columns=['path', 'cls', 'conf', 'x1', 'y1', 'x2', 'y2']).to_parquet(os.path.join(box_dir, tag), index=False)
        pd.DataFrame(stats).to_parquet(os.path.join(stat_dir, tag), index=False)
        done = c + len(part)
        rate = done / (time.time() - t0)
        print('%d/%d images  %.1f img/s  ETA %.0f min' % (done, len(members), rate, (len(members) - done) / rate / 60), flush=True)
    print('chunks', len(glob.glob(os.path.join(stat_dir, '*.parquet'))), 'device', dev)


if __name__ == '__main__':
    main(int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None)

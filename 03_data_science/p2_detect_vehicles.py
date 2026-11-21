import zipfile, csv, os, sys, io, time
from PIL import Image
from ultralytics import YOLO
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'data', 'clean', 'detections.csv')
CLS = {2: 'car', 3: 'motorcycle', 5: 'bus', 7: 'truck'}
FIELDS = ['image_id', 'car', 'motorcycle', 'bus', 'truck', 'vehicles', 'occupancy', 'brightness', 'mean_conf']

def main(src, limit=None, batch=32):
    import torch
    dev = 'mps' if torch.backends.mps.is_available() else 'cuda' if torch.cuda.is_available() else 'cpu'
    model = YOLO('yolov8n.pt')
    zf = zipfile.ZipFile(src)
    raw = {}
    for i in zf.infolist():
        n = i.filename
        if not i.flag_bits & 2048:
            try:
                n = n.encode('cp437').decode('utf-8')
            except Exception:
                pass
        raw[n] = i.filename
    imgs = [r for r in csv.DictReader(open(os.path.join(ROOT, 'data', 'clean', 'images.csv'), encoding='utf-8')) if r['is_broken'] == '0']
    done = set()
    if os.path.exists(OUT):
        done = {r['image_id'] for r in csv.DictReader(open(OUT, encoding='utf-8'))}
    todo = [r for r in imgs if r['image_id'] not in done][:limit]
    new = not os.path.exists(OUT)
    f = open(OUT, 'a', newline='', encoding='utf-8')
    w = csv.DictWriter(f, fieldnames=FIELDS)
    if new:
        w.writeheader()
    t0 = time.time()
    print('device', dev, 'todo', len(todo), 'done before', len(done))
    for k in range(0, len(todo), batch):
        chunk = todo[k:k + batch]
        ims = []
        for r in chunk:
            im = Image.open(io.BytesIO(zf.read(raw[r['path']]))).convert('RGB')
            ims.append(im)
        res = model.predict(ims, imgsz=640, conf=0.25, classes=list(CLS), device=dev, verbose=False)
        for r, im, p in zip(chunk, ims, res):
            c = {v: 0 for v in CLS.values()}
            area = 0.0
            confs = []
            for b, cl, cf in zip(p.boxes.xyxy.tolist(), p.boxes.cls.tolist(), p.boxes.conf.tolist()):
                c[CLS[int(cl)]] += 1
                area += (b[2] - b[0]) * (b[3] - b[1])
                confs.append(cf)
            W, H = im.size
            g = im.convert('L').resize((64, 36))
            w.writerow({'image_id': r['image_id'], **c, 'vehicles': sum(c.values()), 'occupancy': round(min(area / (W * H), 1), 4), 'brightness': round(sum(g.getdata()) / (64 * 36), 1), 'mean_conf': round(sum(confs) / len(confs), 3) if confs else ''})
        f.flush()
        if k // batch % 20 == 0:
            n = k + len(chunk)
            el = time.time() - t0
            print('%d/%d  %.1f img/s  ETA %.0f min' % (n, len(todo), n / el, (len(todo) - n) / (n / el) / 60), flush=True)
    f.close()
    print('done', time.time() - t0)
if __name__ == '__main__':
    lim = int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None
    main(sys.argv[1], lim)

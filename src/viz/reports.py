import html
import json

import pandas as pd

from src.common.config import path, read_json
from src.viz import figures

CSS = """
:root{--bg:#fafaf8;--card:#fff;--ink:#1d1d1f;--muted:#6b6b6b;--line:#e4e4e0;--accent:#2a6fdb;--warm:#e07a1f}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#141416;--card:#1d1d20;--ink:#ececec;--muted:#a0a0a0;--line:#333;--accent:#6f9cf0;--warm:#f0a35c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,'Sarabun','Thonburi',sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:32px 0 8px}
.sub{color:var(--muted);margin:0 0 20px}table{border-collapse:collapse;width:100%;background:var(--card);font-size:13.5px}
th,td{border-bottom:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}th{color:var(--muted);font-weight:600}
td.n{text-align:right;font-variant-numeric:tabular-nums}.tag{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;border:1px solid var(--line)}
.wrap{overflow-x:auto}img{max-width:100%;height:auto;background:#fff;border-radius:6px;border:1px solid var(--line)}
"""


def dq_report():
    dq = read_json('dq_rules.json')
    comp = pd.read_parquet(path('silver', 'image_completeness.parquet'))
    low = comp[comp['completeness'] < 0.9].sort_values('completeness').head(15)
    rows = ''.join('<tr><td>%s</td><td>%s</td><td><span class=tag>%s</span></td><td class=n>%s</td><td class=n>%s</td></tr>'
                   % (html.escape(r['table']), html.escape(r['rule']), r['action'], '{:,}'.format(r['rows_before']), '{:,}'.format(r['rows_affected']))
                   for r in dq)
    lows = ''.join('<tr><td>%s</td><td>%s</td><td class=n>%d</td><td class=n>%d</td><td class=n>%.0f%%</td></tr>'
                   % (r.cam, r.date, r.images, r.valid, r.completeness * 100) for r in low.itertuples())
    frozen = pd.read_parquet(path('silver', 'images.parquet'), columns=['cam', 'is_frozen', 'is_broken'])
    fz = frozen.groupby('cam')[['is_frozen', 'is_broken']].sum().query('is_frozen > 0 or is_broken > 20').sort_values('is_frozen', ascending=False).head(15)
    fzr = ''.join('<tr><td>%s</td><td class=n>%d</td><td class=n>%d</td></tr>' % (c, r.is_frozen, r.is_broken) for c, r in fz.iterrows())
    page = f"""<!doctype html><html lang=th><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Data Quality Report</title><style>{CSS}</style></head><body><main>
<h1>Data Quality Report</h1><p class=sub>ทุกกฎการทำความสะอาดใน Silver layer (PySpark) · ก่อน → จำนวนแถวที่โดน · action: drop = ตัดทิ้ง, flag = ทำเครื่องหมาย, set_null = ค่าผิด→ว่าง, convert/map = แปลงรูปแบบ</p>
<img src="figures/dq_image_funnel.png" alt="image funnel">
<h2>กฎทั้งหมด</h2><div class=wrap><table><tr><th>ตาราง</th><th>กฎ</th><th>action</th><th>ก่อน</th><th>แถวที่โดน</th></tr>{rows}</table></div>
<h2>กล้อง×วันที่ภาพครบไม่ถึง 90% (คาด 91 ภาพ/วัน ทุก 10 นาที 06–21 น.)</h2><div class=wrap><table><tr><th>กล้อง</th><th>วันที่</th><th>ภาพ</th><th>ใช้ได้</th><th>ครบ</th></tr>{lows}</table></div>
<h2>กล้องที่มีภาพค้าง/ภาพเสียมาก</h2><div class=wrap><table><tr><th>กล้อง</th><th>ภาพค้าง</th><th>ภาพเสีย</th></tr>{fzr}</table></div>
</main></body></html>"""
    open(path('reports', 'dq_report.html'), 'w', encoding='utf-8').write(page)


def dashboard_data():
    feat = pd.read_parquet(path('gold', 'features_cam_hr.parquet'))
    prof = pd.read_parquet(path('gold', 'camera_profile.parquet'))
    rows = feat[['cam', 'date', 'hour', 'is_weekend', 'rain_level', 'light', 'n_images', 'veh_mean', 'car_mean', 'moto_mean', 'bus_mean', 'truck_mean', 'cong_mean']].copy()
    rows['cam'] = rows['cam'].astype(int)
    rows = rows.round(3)
    cams = prof[['cam', 'name_th', 'name_en', 'lat', 'lon', 'district', 'highway', 'veh_mean', 'veh_weekday', 'veh_weekend', 'truck_share', 'moto_share',
                 'flood_unfixed_500m', 'in_flood_hotspot', 'poi_food', 'dist_rail_m']].copy().round(3)
    model = read_json('model_report.json')
    pred = pd.read_parquet(path('gold', 'model_predictions_test.parquet')).round(3)
    return {'cols': list(rows.columns), 'rows': rows.values.tolist(), 'cams': cams.to_dict('records'),
            'model': {'runs': model['runs'], 'best': model['best'], 'rf_importance': model.get('rf_importance_F3', {}), 'nowcast': model.get('nowcast'), 'rain_effect': model.get('rain_effect', {}), 'camera_holdout': model.get('camera_holdout', {})},
            'pred': pred[['y', 'yhat', 'is_weekend', 'rain_prev_level']].values.tolist()}


def dashboard():
    data = json.dumps(dashboard_data(), ensure_ascii=False, default=str, separators=(',', ':'))
    tpl = open(path('dashboard', 'template.html'), encoding='utf-8').read()
    open(path('dashboard', 'dashboard.html'), 'w', encoding='utf-8').write(tpl.replace('/*__DATA__*/null', data))


def main():
    from src.viz import insights
    figures.main()
    dq_report()
    dashboard()
    insights.main()
    print('reports written')


if __name__ == '__main__':
    main()

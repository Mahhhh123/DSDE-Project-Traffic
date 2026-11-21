import matplotlib

matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from src.common.config import path, read_json

plt.rcParams.update({'font.family': ['Thonburi', 'Arial Unicode MS', 'DejaVu Sans'], 'font.size': 11, 'axes.spines.top': False,
                     'axes.spines.right': False, 'axes.grid': True, 'grid.color': '#e6e6e6', 'grid.linewidth': 0.8,
                     'axes.axisbelow': True, 'figure.dpi': 110, 'savefig.bbox': 'tight', 'legend.frameon': False})
WEEKDAY, WEEKEND = '#2a6fdb', '#e07a1f'
RAIN = {'dry': '#b8c4d6', 'light': '#5b8ff0', 'heavy': '#1c3f94'}
INK, MUTED = '#222222', '#6b6b6b'


def save(fig, name):
    p = path('reports', 'figures', name)
    fig.savefig(p)
    plt.close(fig)
    return p


def fig_hourly(a):
    d = pd.DataFrame(a['i1']['hourly_profile'])
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(d['hour'], d['weekday'], color=WEEKDAY, lw=2, marker='o', ms=4, label='วันธรรมดา')
    ax.plot(d['hour'], d['weekend'], color=WEEKEND, lw=2, marker='o', ms=4, label='วันหยุด')
    ax.axvspan(18.5, 21.5, color='#f2f2f2', zorder=0)
    ax.text(19.9, ax.get_ylim()[1] * 0.97, 'ฟ้ามืด (YOLO\nนับได้น้อยลง)', ha='center', va='top', fontsize=9, color=MUTED)
    ax.set(xlabel='ชั่วโมง', ylabel='รถเฉลี่ยต่อภาพ (คัน)', xticks=range(6, 22))
    ax.legend(loc='lower center', ncol=2)
    ax.set_title('อินไซต์ 1 · จังหวะการจราจรรายชั่วโมง', loc='left', color=INK)
    return save(fig, 'i1_hourly_profile.png')


def fig_am_pm(a):
    d = a['i2']
    fig, ax = plt.subplots(figsize=(6, 3.6))
    labels = ['ใกล้รถไฟฟ้า ≤500 ม.', 'จุดอื่น']
    vals = [d['median_ratio_near_rail_500m'], d['median_ratio_elsewhere']]
    ax.barh(labels, vals, color=[WEEKDAY, '#9db7e8'], height=0.5)
    ax.axvline(1, color=MUTED, lw=1, ls='--')
    for i, v in enumerate(vals):
        ax.text(v + 0.01, i, '%.2f' % v, va='center')
    ax.set(xlabel='รถช่วงเช้า 07–09 ÷ ช่วงเย็น 16–18 (มัธยฐานของกล้อง)', xlim=(0, 1.15))
    ax.set_title('อินไซต์ 2 · ตอนเย็นหนาแน่นกว่าตอนเช้า', loc='left')
    return save(fig, 'i2_am_pm_rail.png')


def fig_rain(a):
    rows = []
    for key, label in [('i3', 'วันธรรมดา'), ('i4', 'วันหยุด')]:
        block = a['i3']['all_light'] if key == 'i3' else a['i4']['weekend']
        for lv in ['dry', 'light', 'heavy']:
            if lv in block:
                rows.append((label, lv, block[lv]['estimate'], *block[lv]['ci95'], block[lv]['n_images']))
    d = pd.DataFrame(rows, columns=['day', 'lv', 'est', 'lo', 'hi', 'n'])
    fig, ax = plt.subplots(figsize=(8, 3.8))
    x = np.arange(len(d))
    ax.bar(x, d['est'], color=[RAIN[l] for l in d['lv']], width=0.6)
    ax.errorbar(x, d['est'], yerr=[d['est'] - d['lo'], d['hi'] - d['est']], fmt='none', ecolor=INK, capsize=4, lw=1)
    ax.axhline(1, color=MUTED, lw=1, ls='--')
    names = {'dry': 'ไม่ตก', 'light': 'ฝนเบา', 'heavy': 'ฝนหนัก'}
    ax.set_xticks(x, ['%s\n%s\n(n=%s)' % (r.day, names[r.lv], '{:,}'.format(r.n)) for r in d.itertuples()], fontsize=9)
    ax.set(ylabel='ดัชนีความหนาแน่น\n(1.00 = เท่าตอนไม่มีฝน)', ylim=(0, 1.3))
    ax.set_title('อินไซต์ 3–4 · ผลของฝน (ค่ากลางเรขาคณิต + ช่วงเชื่อมั่น 95% แบบ bootstrap รายกล้อง)', loc='left', fontsize=10)
    return save(fig, 'i3_i4_rain_effect.png')


def fig_weekend_places(a):
    d = pd.DataFrame(a['i5']['top_weekend'] + a['i5']['bottom_weekend']).drop_duplicates('cam').sort_values('weekend_ratio')
    fig, ax = plt.subplots(figsize=(7, 4))
    lab = [('%s · %s' % (r.cam, str(r.name_th)[:28])) for r in d.itertuples()]
    ax.barh(lab, d['weekend_ratio'], color=[WEEKEND if v > 1 else WEEKDAY for v in d['weekend_ratio']], height=0.6)
    ax.axvline(1, color=MUTED, lw=1, ls='--')
    ax.set(xlabel='รถวันหยุด ÷ วันธรรมดา')
    ax.set_title('อินไซต์ 5 · กล้องที่วันหยุดคึกที่สุด / เงียบที่สุด', loc='left')
    return save(fig, 'i5_weekend_ratio.png')


def fig_district(a):
    d = pd.DataFrame(a['i6']['district_daylight']).sort_values('veh')
    fig, ax = plt.subplots(figsize=(7, max(3, len(d) * 0.28)))
    ax.barh(d['district'], d['veh'], color='#5b8ff0', height=0.6)
    ax.set(xlabel='รถเฉลี่ยต่อภาพ ช่วงกลางวัน (เขตที่มี ≥2 กล้อง)')
    ax.set_title('อินไซต์ 6 · ความหนาแน่นตามเขต', loc='left')
    return save(fig, 'i6_district.png')


def fig_mix(a):
    d = pd.DataFrame(a['i7']['share_by_highway_pct']).set_index('highway')
    order = [h for h in ['motorway', 'trunk', 'primary', 'secondary', 'tertiary', 'minor'] if h in d.index]
    d = d.loc[order]
    fig, ax = plt.subplots(figsize=(7, 3.8))
    left = np.zeros(len(d))
    cols = {'car': '#b8c4d6', 'motorcycle': '#e07a1f', 'bus': '#2a9d8f', 'truck': '#1c3f94'}
    for c, col in cols.items():
        ax.barh(d.index, d[c], left=left, color=col, label=c, height=0.6, edgecolor='white', linewidth=1.5)
        left += d[c].values
    ax.set(xlabel='สัดส่วนประเภทรถ (%)', xlim=(0, 100))
    ax.legend(ncol=4, loc='upper center', bbox_to_anchor=(0.5, -0.18))
    ax.set_title('อินไซต์ 7 · ประเภทรถตามชนิดถนน (OSM)', loc='left')
    return save(fig, 'i7_vehicle_mix.png')


def fig_truck_hour(a):
    d = pd.DataFrame(a['i7']['truck_share_by_hour_daylight'])
    fig, ax = plt.subplots(figsize=(7, 3.4))
    ax.plot(d['hour'], d['weekday'], color=WEEKDAY, lw=2, marker='o', ms=4, label='วันธรรมดา')
    ax.plot(d['hour'], d['weekend'], color=WEEKEND, lw=2, marker='o', ms=4, label='วันหยุด')
    ax.set(xlabel='ชั่วโมง (เฉพาะช่วงฟ้าสว่าง)', ylabel='รถบรรทุก (% ของรถทั้งหมด)')
    ax.legend()
    ax.set_title('อินไซต์ 7 · รถบรรทุกเลี่ยงชั่วโมงเร่งด่วนวันธรรมดา', loc='left')
    return save(fig, 'i7_truck_by_hour.png')


def fig_models(m):
    d = pd.DataFrame(m['runs'])
    d['label'] = d.apply(lambda r: r['model'] if r['model'].startswith('baseline') else '%s · %s' % (r['model'], r['features']), axis=1)
    d = d.sort_values('mae', ascending=False)
    fig, ax = plt.subplots(figsize=(7.5, max(3, len(d) * 0.33)))
    best = m['best']
    colors = ['#1c3f94' if (r.model == best['model'] and r.features == best['features']) else ('#999999' if r.model.startswith('baseline') else '#9db7e8')
              for r in d.itertuples()]
    ax.barh(d['label'], d['mae'], color=colors, height=0.6)
    for i, v in enumerate(d['mae']):
        ax.text(v + 0.01, i, '%.3f' % v, va='center', fontsize=9)
    ax.set(xlabel='MAE บนชุดทดสอบ 30–31 ส.ค. (คันต่อภาพ) · ยิ่งน้อยยิ่งดี · สีเข้ม = โมเดลที่เลือกด้วย CV')
    ax.set_title('โมเดล · เทียบ baseline และชุด feature', loc='left')
    return save(fig, 'ml_model_comparison.png')


def fig_pred(m):
    d = pd.read_parquet(path('gold', 'model_predictions_test.parquet'))
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter(d['y'], d['yhat'], s=8, alpha=0.35, color='#2a6fdb', edgecolor='none')
    lim = max(d['y'].max(), d['yhat'].max()) * 1.05
    ax.plot([0, lim], [0, lim], color=MUTED, lw=1, ls='--')
    ax.set(xlim=(0, lim), ylim=(0, lim), xlabel='ค่าจริง (รถเฉลี่ยต่อภาพ ในชั่วโมงนั้น)', ylabel='ค่าทำนาย')
    t = m['best']['test']
    ax.set_title('ค่าจริง vs ทำนาย · MAE %.2f · R² %.2f' % (t['mae'], t['r2']), loc='left')
    return save(fig, 'ml_actual_vs_pred.png')


def fig_importance(m):
    imp = m['best'].get('importance') or m.get('rf_importance_F3') or {}
    if not imp:
        return None
    d = pd.Series(imp).head(15).sort_values()
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.barh(d.index, d.values, color='#5b8ff0', height=0.6)
    ax.set(xlabel='Feature importance (Random Forest, feature set F3)')
    ax.set_title('ตัวแปรที่โมเดลใช้มากที่สุด', loc='left')
    return save(fig, 'ml_feature_importance.png')


def fig_rain_mae(m):
    g = m['best']['by_group']
    keys = [('rain_prev_level=dry', 'ไม่ตก'), ('rain_prev_level=light', 'ฝนเบา'), ('rain_prev_level=heavy', 'ฝนหนัก')]
    keys = [(k, l) for k, l in keys if k in g]
    x = np.arange(len(keys))
    fig, ax = plt.subplots(figsize=(6.5, 3.6))
    b = [g[k]['baseline']['mae'] for k, _ in keys]
    mm = [g[k]['model']['mae'] for k, _ in keys]
    ax.bar(x - 0.18, b, width=0.34, color='#b8c4d6', label='baseline (ค่าเฉลี่ยประวัติกล้อง×ชั่วโมง)')
    ax.bar(x + 0.18, mm, width=0.34, color='#1c3f94', label='โมเดล + ข้อมูลฝน/พื้นที่')
    for i in range(len(keys)):
        ax.text(x[i] + 0.18, mm[i] + 0.02, '%+.0f%%' % ((mm[i] / b[i] - 1) * 100), ha='center', fontsize=9)
    ax.set_xticks(x, ['%s\n(n=%d)' % (l, g[k]['n']) for k, l in keys])
    ax.set(ylabel='MAE (คัน/ภาพ)')
    ax.legend(loc='upper left')
    ax.set_title('ข้อมูลฝนที่ scrape มาช่วยทำนายตอนฝนตกได้มากที่สุด', loc='left')
    return save(fig, 'ml_mae_by_rain.png')


def fig_dq(dq):
    d = {r['rule']: r for r in dq if r['table'] == 'images'}
    total = next(iter(d.values()))['rows_before']
    broken = next(r['rows_affected'] for k, r in d.items() if k.startswith('broken'))
    stale = next(r['rows_affected'] for k, r in d.items() if k.startswith('stale'))
    valid = next(r['rows_affected'] for k, r in d.items() if k.startswith('valid'))
    parsed = total - sum(r['rows_affected'] for r in d.values() if r['action'] == 'drop')
    steps = [('ไฟล์ภาพใน zip', total), ('ชื่อไฟล์ / เวลา / ไม่ซ้ำ ผ่าน', parsed), ('ตัดภาพเสีย −{:,}'.format(broken), parsed - broken),
             ('ตัดภาพค้าง (ซ้ำภาพก่อนหน้า) −{:,}'.format(stale), valid)]
    s = pd.DataFrame(steps, columns=['step', 'n'])
    fig, ax = plt.subplots(figsize=(7.5, 2.8))
    ax.barh(s['step'][::-1], s['n'][::-1], color='#5b8ff0', height=0.6)
    for i, v in enumerate(s['n'][::-1]):
        ax.text(v, i, ' {:,}'.format(int(v)), va='center', fontsize=9)
    ax.set(xlabel='จำนวนภาพ', xlim=(0, total * 1.15))
    ax.set_title('Data cleaning · ภาพที่เหลือในแต่ละขั้น', loc='left')
    return save(fig, 'dq_image_funnel.png')


def main():
    a = read_json('analysis.json')
    m = read_json('model_report.json')
    dq = read_json('dq_rules.json')
    out = [fig_hourly(a), fig_am_pm(a), fig_rain(a), fig_weekend_places(a), fig_district(a), fig_mix(a), fig_truck_hour(a),
           fig_models(m), fig_pred(m), fig_importance(m), fig_rain_mae(m), fig_dq(dq)]
    print('figures', len([o for o in out if o]))


if __name__ == '__main__':
    main()

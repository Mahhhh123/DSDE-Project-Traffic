import html

from src.common.config import path, read_json
from src.viz.reports import CSS

EXTRA = """
.ins{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:18px 0}
.ins h2{margin:0 0 10px;font-size:19px}.lbl{display:inline-block;min-width:78px;font-weight:650;color:var(--accent)}
.ins p{margin:6px 0}.src{font-size:12.5px;color:var(--muted);margin-top:8px}.neg{color:var(--warm)}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0}.k{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 12px}
.k b{display:block;font-size:22px}.k span{color:var(--muted);font-size:12.5px}
@media (max-width:760px){.kpis{grid-template-columns:repeat(2,1fr)}}
"""


def pct(x):
    return '%+.0f%%' % ((x - 1) * 100)


def ci(b):
    return '%.2f (95%% CI %.2f–%.2f)' % (b['estimate'], b['ci95'][0], b['ci95'][1])


def block(n, title, context, insight, evidence, action, sources, figs=()):
    imgs = ''.join('<p><img src="figures/%s" alt="%s"></p>' % (f, html.escape(title)) for f in figs)
    return f"""<section class=ins><h2>{n}. {title}</h2>
<p><span class=lbl>Context</span>{context}</p><p><span class=lbl>Insight</span>{insight}</p>
<p><span class=lbl>Evidence</span>{evidence}</p><p><span class=lbl>Action</span>{action}</p>{imgs}
<p class=src>แหล่งข้อมูล: {sources}</p></section>"""


def main():
    a, m, dq = read_json('analysis.json'), read_json('model_report.json'), read_json('dq_rules.json')
    sp = read_json('spatial_summary.json')
    i1, i2, i3, i4, i5, i6, i7 = (a['i%d' % k] for k in range(1, 8))
    best, g = m['best'], m['best']['by_group']
    base = next(r for r in m['runs'] if r['model'] == 'baseline_history_profile')
    rf3 = next(r for r in m['runs'] if r['model'] == 'random_forest' and r['features'] == 'F3_+location')
    nc = min((r for r in m['runs'] if 'lag1' in r['features']), key=lambda r: r['mae'])
    imp_rule = lambda s: next(r for r in dq if r['rule'].startswith(s))
    corr = i1['weekday_profile_corr_matrix']
    tf = [corr[x][y] for x in corr for y in corr if x < y and '2026-08-31' not in (x, y)]
    mon = [corr['2026-08-31'][y] for y in corr if y != '2026-08-31']
    ev = i6['weekday_evening_16_18_by_day']
    th = {r['hour']: r for r in i7['truck_share_by_hour_daylight']}
    mix = {r['highway']: r for r in i7['share_by_highway_pct']}
    top, bot = i5['top_weekend'], i5['bottom_weekend']
    dist = i6['district_daylight']
    hw = {r['highway']: r['median'] for r in i6['highway_veh_median']}
    wx = best.get('weather_coefficients_pct', {})
    lr, hr = g['rain_prev_level=light'], g.get('rain_prev_level=heavy')
    mmd = {k.split('[T.')[-1].rstrip(']') if ':' not in k else 'light_we' if 'light' in k else 'heavy_we': v for k, v in i3['mixed_model'].items()}
    mm_light, mm_heavy, mm_light_we = mmd['light'], mmd['heavy'], mmd['light_we']

    blocks = [
        block(1, 'วันธรรมดามีสองยอด (เช้า–เย็น) · วันหยุดมียอดเดียวตอนเที่ยง',
              'คนเมืองเดินทางตามตารางงาน/เรียน วันหยุดไม่มีแรงบังคับนี้',
              f"วันธรรมดายอดแรก {i1['weekday_am_peak']['hour']:02d}:00 ({i1['weekday_am_peak']['veh']:.2f} คัน/ภาพ) และยอดที่สูงกว่า {i1['weekday_pm_peak']['hour']:02d}:00 ({i1['weekday_pm_peak']['veh']:.2f}) · "
              f"วันหยุดยอดเดียว {i1['weekend_peak']['hour']:02d}:00 ({i1['weekend_peak']['veh']:.2f}) และรถน้อยกว่าวันธรรมดา {abs(i1['weekend_vs_weekday_daylight_pct']):.0f}% ในช่วงฟ้าสว่าง",
              f"รูปแบบรายชั่วโมงของ อ.–ศ. คล้ายกัน (สหสัมพันธ์ {min(tf):.2f}–{max(tf):.2f}) แต่จันทร์ 31 ส.ค. ต่างออกไป ({min(mon):.2f}–{max(mon):.2f}) เพราะฝนตกช่วงบ่าย · ปฏิทินวันหยุดยืนยันว่าสัปดาห์นี้ไม่มีวันหยุดราชการ (ทุกวันจันทร์–ศุกร์เป็นวันทำงานปกติ)",
              'ตั้งเวลาเพิ่มเจ้าหน้าที่จราจร/สัญญาณไฟแยกตามประเภทวัน: วันธรรมดาเน้น 07:00 และ 16:00–18:00 วันหยุดเน้น 11:00–13:00',
              'ภาพ CCTV + YOLO · timeanddate (s5) · sunrise-sunset (s4) ใช้ตัดช่วงหลัง 18:30 ที่ฟ้ามืดออกจากการเทียบ', ['i1_hourly_profile.png']),
        block(2, 'ตอนเย็นหนาแน่นกว่าตอนเช้า',
              'ขาเย็นมีทั้งกลับบ้านและธุระอื่นปนกัน ขาเช้ามีเป้าหมายเดียวแต่เวลาออกจากบ้านกระจายกว่า',
              f"{i2['cams_evening_heavier']} กล้องมีรถช่วง 16–18 น. มากกว่าช่วง 07–09 น. เกิน 10% เทียบกับ {i2['cams_morning_heavier']} กล้องที่กลับกัน · ชั่วโมงที่เป็นยอดของกล้องมากที่สุดคือ 17:00 ({i2['peak_hour_distribution'].get('17', 0)} กล้อง)",
              f"ถนนรอง (tertiary) เอียงไปทางเย็นมากที่สุด (เช้า/เย็น {i2['ratio_by_highway'].get('tertiary', float('nan')):.2f}) ส่วนถนนหลัก {i2['ratio_by_highway'].get('primary', float('nan')):.2f} · "
              f"<span class=neg>สมมติฐานว่ากล้องใกล้สถานีรถไฟฟ้า (≤500 ม., OSM) จะเช้าเบากว่า ไม่ได้รับการยืนยัน: {i2['median_ratio_near_rail_500m']:.2f} vs {i2['median_ratio_elsewhere']:.2f}, p = {i2['mannwhitney_p_near_vs_else']:.2f}</span>",
              'งานถนน/ปิดช่องจราจรควรเลี่ยง 16:00–18:00 มากกว่าช่วงเช้า',
              'ภาพ CCTV + YOLO · OpenStreetMap (s6) ชนิดถนนและสถานีรถไฟฟ้า · sunrise-sunset (s4)', ['i2_am_pm_rail.png']),
        block(3, 'ฝนตกวันธรรมดา กล้องเห็นรถน้อยลง 15–30%',
              'ฝนทำให้คนเลื่อนการเดินทาง และรถที่วิ่งอยู่ช้าลง/เว้นระยะมากขึ้น',
              f"ดัชนีความหนาแน่น (1.00 = เท่าตอนไม่ฝนของกล้อง×ชั่วโมงเดียวกัน) ฝนเบา {ci(i3['all_light']['light'])} · ฝนหนัก {ci(i3['all_light']['heavy'])} · "
              f"เฉพาะตอนฟ้าสว่างยังลดลง: ฝนเบา {ci(i3['daylight_only']['light'])} จึงไม่ได้เกิดจากความมืดอย่างเดียว",
              f"Mixed-effects model (สุ่มตามกล้อง คุมชั่วโมงและแสง): ฝนเบา {mm_light['pct_change']:+.0f}%, ฝนหนัก {mm_heavy['pct_change']:+.0f}% (p &lt; 0.001) · "
              f"METAR สนามบินรายงานฝน {i3['metar_agreement']['hours_metar_rain']} ชม. ตรงกับชั่วโมงที่สถานี กทม. วัดฝนได้ ≥10% ของเมือง {i3['metar_agreement']['of_which_city_share_gt_10pct']} ชม. · "
              f"<span class=neg>ถ้าใช้ Open-Meteo แทนสถานีจริง จะนับว่าฝนตก {i3['openmeteo_vs_station']['images_rain_openmeteo']:,} ภาพ (สถานีจริง {i3['openmeteo_vs_station']['images_rain_station']:,}) และผลของฝนหายไป ({i3['openmeteo_vs_station']['weekday_effect_if_openmeteo_used']['light']['estimate']:.2f}) → ต้องใช้ข้อมูลสถานีที่ scrape มา</span>",
              'เมื่อเรดาร์/สถานีบอกว่าฝนกำลังเข้า ให้เตรียมแผนจราจรช่วงเย็นวันธรรมดา และแจ้งเตือนผู้ขับขี่ล่วงหน้า',
              'ภาพ CCTV + YOLO · สถานีวัดฝน กทม. (s1) · METAR (s2) · Open-Meteo (s3) · sunrise-sunset (s4)', ['i3_i4_rain_effect.png']),
        block(4, 'ฝนวันหยุดแทบไม่เปลี่ยนจำนวนรถ และไม่พบน้ำท่วมถนนรอบกล้อง',
              'วันหยุดคนเลือกเวลาเดินทางได้ และไม่ต้องรีบไปทำงาน',
              f"วันหยุด: ไม่ตก {ci(i4['weekend']['dry'])} · ฝนเบา {ci(i4['weekend']['light'])} · ฝนหนัก {ci(i4['weekend']['heavy'])} → ไม่ต่างจากตอนไม่ฝนอย่างมีนัยสำคัญ · ใน mixed model ผลของฝนเบาวันหยุดต่างจากวันธรรมดา {mm_light_we['pct_change']:+.0f}% (p &lt; 0.001)",
              f"สถานีวัดน้ำท่วมถนน กทม. ภายใน 1 กม. ของ {i4['flood_sensors']['cams_with_sensor']} กล้อง วัดได้ {i4['flood_sensors']['readings_above_0cm']} ครั้งที่ระดับ &gt; 0 ซม. ตลอดสัปดาห์ · "
              f"<span class=neg>กล้องที่มีจุดเสี่ยงน้ำท่วม 'ยังไม่แก้ไข' ใน 500 ม. ({i4['unfixed_flood_points']['cams_with_unfixed_500m']} กล้อง) ไม่ได้ลดลงตอนฝนมากกว่า (p = {i4['unfixed_flood_points']['mannwhitney_p']:.2f}) · DBSCAN พบ hotspot {sp['dbscan']['clusters']} กลุ่ม แต่มีกล้องอยู่ในนั้นแค่ {sp['dbscan']['cameras_in_hotspot']} ตัว · ความหนาแน่น KDE ไม่สัมพันธ์ (ρ = {i4['kde_vs_rain_ratio']['rho']:.2f})</span>",
              'สัปดาห์นี้ฝนไม่แรงพอให้น้ำท่วมถนน ผลของฝนจึงมาจากพฤติกรรมคน ไม่ใช่ถนนใช้ไม่ได้ · ควรเก็บข้อมูลช่วงพายุใหญ่เพิ่มเพื่อทดสอบจุดเสี่ยงอีกครั้ง',
              'สถานีวัดน้ำท่วมถนน กทม. (s8) · BMA Open Data จุดเสี่ยงน้ำท่วม 737 จุด + ปี 2568 + สถิติ 2566 (s9) · GeoPandas buffer/sjoin, KDE, DBSCAN', []),
        block(5, 'วันหยุดคึกหรือเงียบ ขึ้นกับว่าแถวนั้นเป็นย่านทำงานหรือย่านพักผ่อน',
              'ย่านสำนักงานคนหายไปวันหยุด ส่วนสวนสาธารณะ/วัด/ตลาดคนมามากขึ้น',
              f"ค่ากลางวันหยุด÷วันธรรมดา = {i5['median_ratio']:.2f} · คึกขึ้น: กล้อง {top[0]['cam']} หน้าวัดเสาหิน ({top[0]['weekend_ratio']:.2f}), {top[1]['cam']} หน้าสวนจตุจักร ({top[1]['weekend_ratio']:.2f}) · "
              f"เงียบที่สุด: ถนนนราธิวาสฯ กล้อง {bot[0]['cam']} ({bot[0]['weekend_ratio']:.2f}) และ {bot[1]['cam']} ({bot[1]['weekend_ratio']:.2f}), หน้า ปตท. วิภาวดี {bot[2]['cam']} ({bot[2]['weekend_ratio']:.2f})",
              f"จำนวนสถานีรถไฟฟ้ารอบกล้อง (OSM 300 ม.) สัมพันธ์กับวันหยุดที่คึกกว่า (ρ = {i5['poi_spearman']['poi_rail_station']['rho']:.2f}, p = {i5['poi_spearman']['poi_rail_station']['p']:.3f}) · "
              f"<span class=neg>จำนวนห้าง/ตลาด/สำนักงานไม่สัมพันธ์ (|ρ| ≤ {max(abs(i5['poi_spearman'][k]['rho']) for k in ['poi_mall','poi_market','poi_office']):.2f})</span> แปลว่าสถานที่สำคัญเฉพาะจุดสำคัญกว่าจำนวนสถานที่",
              'วันหยุดลดรอบสัญญาณไฟ/เจ้าหน้าที่ในย่านธุรกิจ (สาทร–นราธิวาส, วิภาวดี) และย้ายไปจุดสวน/วัด/ตลาดนัด',
              'ภาพ CCTV + YOLO · OpenStreetMap (s6) สถานที่ 9 ประเภทรอบกล้อง · timeanddate (s5)', ['i5_weekend_ratio.png']),
        block(6, 'ฝั่งธนฯ–ราชเทวีหนาแน่นสุด · พระนคร/ดุสิตน้อยสุด · เย็นวันศุกร์หนักสุด',
              'กล้องในเขตเมืองเก่าอยู่บนถนนเล็กกว่าและมีข้อจำกัดการจราจร',
              f"ช่วงฟ้าสว่าง: {dist[0]['district']} {dist[0]['veh']:.1f}, {dist[1]['district']} {dist[1]['veh']:.1f}, {dist[2]['district']} {dist[2]['veh']:.1f} คัน/ภาพ · น้อยสุด {dist[-1]['district']} {dist[-1]['veh']:.1f}, {dist[-2]['district']} {dist[-2]['veh']:.1f}, {dist[-3]['district']} {dist[-3]['veh']:.1f} · "
              f"เย็นวันธรรมดา 16–18 น.: ศุกร์ {ev['Fri']:.2f} vs อ.–พฤ. {min(ev['Tue'], ev['Wed'], ev['Thu']):.2f}–{max(ev['Tue'], ev['Wed'], ev['Thu']):.2f} (จันทร์ {ev['Mon']:.2f} ฝนตก)",
              f"ค่ากลางตามชนิดถนน (OSM): motorway {hw.get('motorway', 0):.1f} &gt; primary {hw.get('primary', 0):.1f} &gt; secondary {hw.get('secondary', 0):.1f} &gt; tertiary {hw.get('tertiary', 0):.1f} · <span class=neg>แต่ยังไม่มีนัยสำคัญ (Kruskal–Wallis p = {i6['kruskal_highway_p']:.2f}) เพราะมุมกล้องต่างกันมาก</span>",
              'บ่ายวันศุกร์ควรเปิดช่องพิเศษ/ขยายรอบไฟเขียวก่อนวันอื่น · ใช้ตัวเลขรายเขตจัดลำดับการลงทุน',
              'ภาพ CCTV + YOLO · ตารางกล้อง (พิกัด) + สถานีฝน กทม. (เขต) · OpenStreetMap (s6)', ['i6_district.png']),
        block(7, 'ประเภทรถต่างกันตามถนนและย่าน · รถบรรทุกเลี่ยงชั่วโมงเร่งด่วน',
              'ข้อบังคับเวลาห้ามรถบรรทุกเข้าเมือง และย่านร้านอาหาร/สำนักงานมีมอเตอร์ไซค์ส่งของมาก',
              f"รถบรรทุกสูงสุดบน motorway ({mix['motorway']['truck']:.1f}%) · รถบัสบน primary ({mix['primary']['bus']:.1f}%) · มอเตอร์ไซค์บน secondary ({mix['secondary']['motorcycle']:.1f}%) · "
              f"วันธรรมดารถบรรทุก {th[7]['weekday']:.1f}% ตอน 07:00 และ {th[17]['weekday']:.1f}% ตอน 17:00 เทียบกับ {th[10]['weekday']:.1f}% ตอน 10:00",
              f"สัดส่วนมอเตอร์ไซค์สัมพันธ์กับจำนวนร้านอาหารรอบกล้อง (ρ = {i7['moto_vs_food_spearman']['rho']:.2f}, p = {i7['moto_vs_food_spearman']['p']:.3f}) สูงสุดที่ {i7['top_moto_cams'][0]['name_th']} {i7['top_moto_cams'][0]['moto_share']*100:.0f}% (ร้านอาหาร {i7['top_moto_cams'][0]['poi_food']:.0f} แห่ง สำนักงาน {i7['top_moto_cams'][0]['poi_office']:.0f} แห่ง ใน 300 ม.)",
              'จุดที่มอเตอร์ไซค์หนาแน่นควรมีที่จอดรับส่งอาหาร · ตรวจการบังคับใช้เวลาห้ามรถบรรทุกบนทางด่วนช่วงเร่งด่วน',
              'ภาพ CCTV + YOLO (แยก 4 ประเภท) · OpenStreetMap (s6) · sunrise-sunset (s4)', ['i7_vehicle_mix.png', 'i7_truck_by_hour.png']),
    ]

    model = f"""<section class=ins><h2>โมเดลทำนาย (Spark ML)</h2>
<p><span class=lbl>โจทย์</span>ทำนายรถเฉลี่ยต่อภาพของแต่ละกล้องในแต่ละชั่วโมง เทรน 25–29 ส.ค. ทดสอบ 30–31 ส.ค. (แบ่งตามเวลา) จูนด้วย forward-chaining 2 รอบ</p>
<p><span class=lbl>ผล</span>baseline (ค่าเฉลี่ยประวัติกล้อง×ชั่วโมง×ประเภทวัน) MAE {base['mae']:.3f} · โมเดลที่เลือกด้วย CV: {best['model']} {best['features']} MAE {best['test']['mae']:.3f}, R² {best['test']['r2']:.3f} ·
Random Forest F3 MAE {rf3['mae']:.3f} · ถ้ารู้จำนวนรถชั่วโมงก่อนหน้า (nowcast) MAE {nc['mae']:.3f}, R² {nc['r2']:.3f}</p>
<p><span class=lbl>ฝนช่วยไหม</span>ในชั่วโมงที่ฝนเบา MAE ลดจาก {lr['baseline']['mae']:.2f} เหลือ {lr['model']['mae']:.2f} ({(lr['model']['mae']/lr['baseline']['mae']-1)*100:+.0f}%)"""
    if hr:
        model += f" · ฝนหนัก {hr['baseline']['mae']:.2f} → {hr['model']['mae']:.2f} ({(hr['model']['mae']/hr['baseline']['mae']-1)*100:+.0f}%)"
    model += f""" · ตัวแปรฝนที่สำคัญที่สุดคือ สัดส่วนสถานีทั่วเมืองที่ฝนตกในชั่วโมงก่อน (ถ้าตกทั้งเมือง โมเดลคาดว่ารถลด {abs(wx.get('city_rain_share_prev_i', 0)):.0f}%)</p>
<p><span class=lbl>ข้อจำกัด</span><span class=neg>ทำนายกล้องที่ไม่เคยเห็นไม่ได้ (R² {m['camera_holdout']['time+weather']['r2']:.2f}; เพิ่มข้อมูลพื้นที่จาก OSM แล้วแย่ลงเป็น {m['camera_holdout']['time+weather+location']['r2']:.2f}) → ระดับรถของแต่ละกล้องขึ้นกับมุมกล้องมากกว่าลักษณะพื้นที่</span></p>
<p><img src="figures/ml_model_comparison.png" alt="models"></p><p><img src="figures/ml_mae_by_rain.png" alt="mae by rain"></p><p><img src="figures/ml_feature_importance.png" alt="importance"></p></section>"""

    broken, stale = imp_rule('broken')['rows_affected'], imp_rule('stale')['rows_affected']
    page = f"""<!doctype html><html lang=th><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Rain and Traffic Insights</title><style>{CSS}{EXTRA}</style></head><body><main>
<h1>ฝนตกกับรถติดในกรุงเทพฯ · 7 อินไซต์</h1>
<p class=sub>CCTV 100 กล้อง · 25–31 ส.ค. 2569 · ทุกตัวเลขสร้างจาก <code>reports/analysis.json</code> และ <code>reports/model_report.json</code> (คำนวณจาก Gold layer)</p>
<div class=kpis><div class=k><b>{a['images_analysed']:,}</b><span>ภาพที่ใช้วิเคราะห์ (ตัดภาพเสีย {broken} + ภาพค้าง {stale})</span></div>
<div class=k><b>{a['vehicles_counted']:,}</b><span>คันที่ YOLOv8 นับได้</span></div><div class=k><b>8</b><span>แหล่งข้อมูลที่ scrape เพิ่ม</span></div>
<div class=k><b>{best['test']['mae']:.2f}</b><span>MAE โมเดลบนวันทดสอบ (baseline {base['mae']:.2f})</span></div></div>
{''.join(blocks)}
{model}
<section class=ins><h2>ข้อจำกัด</h2><p>ข้อมูล 7 วัน · ไม่มีฝนช่วงเช้า · ภาพหาย 27 ส.ค. 06–09 น. · YOLO สำเร็จรูปนับได้น้อยลงตอนมืดและนับมอเตอร์ไซค์ขาด (ต้องยืนยันด้วยการนับมือ 200 ภาพ: <code>reports/label_tool.html</code>) · สถานีฝนอยู่ห่างกล้องเฉลี่ย {sp['station_dist_m_median']:.0f} ม. · เว็บ กทม. แสดงแค่ 51 สถานีที่ฝนมากสุดต่อชั่วโมง (สถานีที่ไม่แสดงถูกแทนเป็น 0 เมื่อแถวสุดท้ายเป็น 0) · ผลเป็นความสัมพันธ์ ไม่ใช่เหตุและผล</p></section>
</main></body></html>"""
    out = path('reports', 'insights.html')
    open(out, 'w', encoding='utf-8').write(page)
    print('insights', out)


if __name__ == '__main__':
    main()

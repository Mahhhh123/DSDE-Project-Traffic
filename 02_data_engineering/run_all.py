import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else None
FORCE = '--force' in sys.argv
SKIP_SCRAPE = '--skip-scrape' in sys.argv
SKIP_DETECT = '--skip-detect' in sys.argv

STEPS = [
    ('P0 ตารางกล้อง', None, ['02_data_engineering/p0_cameras.py']),
    ('S5 วันหยุด/ประเภทวัน', 'day_type.csv', ['01_scraping/s5_holidays.py']),
    ('S1 ฝนสถานี กทม.', 'bma_rain_hourly.csv', ['01_scraping/s1_bma_rain.py']),
    ('S2 METAR สนามบิน', 'metar_30min.csv', ['01_scraping/s2_metar_airports.py']),
    ('S3 Open-Meteo', 'openmeteo_hourly.csv', ['01_scraping/s3_openmeteo.py']),
    ('S4 พระอาทิตย์ขึ้น/ตก', 'sun_daily.csv', ['01_scraping/s4_sun.py']),
    ('S6 OpenStreetMap ถนนและสถานที่', 'osm_camera_context.csv', ['01_scraping/s6_osm_roads.py']),
    ('S8 น้ำท่วมถนน กทม.', 'bma_road_flood_hourly.csv', ['01_scraping/s8_bma_road_flood.py']),
    ('S9 จุดเสี่ยงน้ำท่วม กทม.', 'flood_risk_points.csv', ['01_scraping/s9_bma_flood_risk.py']),
    ('P1 ดัชนีภาพ', 'images.csv', ['02_data_engineering/p1_index_images.py', '<zip>']),
    ('P2 นับรถ YOLO', None, ['03_data_science/p2_detect_vehicles.py', '<zip>']),
    ('P3 รวมตาราง fact', None, ['02_data_engineering/p3_build_tables.py']),
    ('P4 ข้อมูลแดชบอร์ด', None, ['03_data_science/p4_dashboard_data.py']),
    ('P6 เชื่อมข้อมูลน้ำท่วม', None, ['03_data_science/p6_flood_join.py']),
]


def exists(name):
    return os.path.exists(os.path.join(ROOT, 'data', 'clean', name))


for name, out, cmd in STEPS:
    if SKIP_SCRAPE and name.startswith('S'):
        continue
    if SKIP_DETECT and name.startswith('P2'):
        continue
    if out and exists(out) and not FORCE:
        print('· ข้าม', name, '(มี', out, 'แล้ว)')
        continue
    if '<zip>' in cmd:
        if not ZIP:
            sys.exit('✗ %s ต้องระบุไฟล์ cctv_images.zip' % name)
        cmd = [ZIP if c == '<zip>' else c for c in cmd]
    start = time.time()
    print('▶', name, flush=True)
    result = subprocess.run([sys.executable, os.path.basename(cmd[0])] + cmd[1:], cwd=os.path.join(ROOT, os.path.dirname(cmd[0])))
    if result.returncode:
        sys.exit('✗ %s ล้มเหลว (exit %d)' % (name, result.returncode))
    print('✓ %s %.0f วิ' % (name, time.time() - start))
print('เสร็จทุกขั้น → เปิด 04_dashboard/dashboard.html')

# DSDE Project: ฝนตกกับรถติดในกรุงเทพฯ (Bangkok CCTV Rain & Traffic)

โปรเจกต์วิชา 2110403 Data Science and Data Engineering (DSDE-CEDT) ภาคเรียน 2026/1

**คำถาม:** ฝนตกทำให้ความหนาแน่นของรถที่กล้อง CCTV ของ กทม. มองเห็นเปลี่ยนไปอย่างไร แยกตามช่วงเวลาของวัน และวันธรรมดากับวันหยุด

- วิดีโอนำเสนอ: _(ใส่ลิงก์ YouTube)_
- สไลด์: _(ใส่ลิงก์ PDF)_
- แดชบอร์ด: เปิด `04_dashboard/dashboard.html` ด้วยเบราว์เซอร์

## ข้อมูล

| แหล่ง | ประเภท | สคริปต์ | ผลลัพธ์ |
|---|---|---|---|
| ภาพ CCTV 100 กล้อง (BMA Traffic) 61,319 ภาพ, 25–31 ส.ค. 2569, 06:00–21:00 ทุก 10 นาที | ข้อมูลจากอาจารย์ (ไม่ได้ใส่ในรีโป) | – | `data/clean/images.csv` |
| ตารางกล้องและพิกัด | ข้อมูลจากอาจารย์ | `02_data_engineering/p0_cameras.py` | `data/cameras.csv` |
| ระบบตรวจวัดปริมาณน้ำฝน สำนักการระบายน้ำ กทม. (123 สถานี) | Web scraping (ส่งฟอร์ม + อ่านตาราง HTML) | `01_scraping/s1_bma_rain.py` | `bma_rain_hourly.csv`, `bma_rain_stations.csv` |
| METAR สนามบินดอนเมือง/สุวรรณภูมิ (Iowa Environmental Mesonet) | API | `01_scraping/s2_metar_airports.py` | `metar_30min.csv` |
| Open-Meteo Historical Weather | API | `01_scraping/s3_openmeteo.py` | `openmeteo_hourly.csv` |
| sunrise-sunset.org | API | `01_scraping/s4_sun.py` | `sun_daily.csv` |
| timeanddate.com ปฏิทินวันหยุดไทย | Web scraping (ตาราง HTML) | `01_scraping/s5_holidays.py` | `holidays_2026.csv`, `day_type.csv` |
| สถานีวัดน้ำท่วมถนน สำนักการระบายน้ำ กทม. | Web scraping (ส่งฟอร์ม + อ่านตาราง HTML) | `01_scraping/s8_bma_road_flood.py` | `bma_road_flood_hourly.csv`, `bma_road_flood_sensors.csv` |
| BMA Open Data: จุดเสี่ยงน้ำท่วม 737 จุด (สถานะการแก้ไข), จุดเสี่ยงปี 2568, สถิติน้ำท่วมถนน 2566 | API (CKAN) | `01_scraping/s9_bma_flood_risk.py` | `flood_risk_points.csv`, `flood_risk_points_2568.csv`, `road_flood_events_2566.csv` |
| OpenStreetMap Overpass / Nominatim | API (ยังไม่ได้ใช้ในผลหลัก) | `s6_osm_roads.py`, `s7_geocode_cameras.py` | – |

ทุกคำขอที่ scrape ถูกบันทึกใน `data/raw/scrape_log.csv`

## Pipeline

```
cctv_images.zip ─► P1 ดัชนีภาพ + คัดภาพเสีย ─► P2 นับรถ YOLOv8n ─┐
cctv_info.csv  ─► P0 ตารางกล้อง (พิกัด) ─────────────────────────┤
Scraping S1–S5, S8–S9 (ฝน, อากาศ, แสง, วันหยุด, น้ำท่วม) ────────────────────────┼─► P3 ตาราง fact (1 แถว/ภาพ) ─► P4 สรุป ─► Dashboard
                                                                   └─► analysis.ipynb (สถิติ + insights)
```

| โฟลเดอร์ | ส่วนตามเกณฑ์ | ไฟล์ |
|---|---|---|
| `01_scraping/` | งานบังคับ Web scraping | `common.py`, `s1`–`s7` |
| `02_data_engineering/` | Component 1 | `p0_cameras.py`, `p1_index_images.py`, `p3_build_tables.py`, `run_all.py` |
| `03_data_science/` | Component 2 | `p2_detect_vehicles.py`, `p4_dashboard_data.py`, `p5_label_sample.py`, `p6_flood_join.py`, `analysis.ipynb` |
| `04_dashboard/` | Component 3 | `dashboard.html`, `camera_map.html` |
| `05_insights/` | Component 4 | `summary.html` |
| `docs/` | แผนงาน | `project_plan.html` |
| `data/` | ข้อมูลที่ scrape และตารางที่ทำความสะอาดแล้ว | `raw/`, `clean/` |

## วิธีรัน

```bash
pip install -r requirements.txt          # ต้องใช้ Python 3.10–3.12 (สำหรับ torch/ultralytics)

python 02_data_engineering/run_all.py /path/to/cctv_images.zip
python 02_data_engineering/run_all.py --skip-scrape --skip-detect   # ใช้ข้อมูลใน data/ ที่มีอยู่แล้ว ไม่ต้องมีไฟล์ภาพ
```

- `run_all.py` รันทุกขั้นตามลำดับ ข้ามขั้นที่มีไฟล์ผลแล้ว (`--force` เพื่อรันใหม่)
- `p2_detect_vehicles.py` รันต่อจากจุดที่ค้างได้ ใช้ GPU (mps/cuda) ถ้ามี
- `python 01_scraping/s1_bma_rain.py --test` ลองดึง 1 ช่วงเวลา (เขียนไฟล์ `_test.csv` แยก ไม่ทับข้อมูลจริง)
- `python 03_data_science/p5_label_sample.py <zip>` สุ่ม 200 ภาพให้นับมือ แล้ว `--score` เพื่อวัดความแม่นของ YOLO

## นิยาม

- ช่วงเวลา: เช้า 06–09 · สาย 09–12 · บ่าย 12–16 · เย็น 16–19 · ค่ำ 19–21
- ประเภทวัน: วันธรรมดา 25–28, 31 ส.ค. · วันหยุด 29–30 ส.ค. (ไม่มีวันหยุดราชการในช่วงนี้)
- ฝนของชั่วโมง h = ฝน 1 ชม. ที่รายงานเวลา h+1 ของสถานีที่ใกล้กล้องที่สุด (ค่ากลาง 0.86 กม.) · ไม่ตก < 0.5 · เบา 0.5–5 · หนัก ≥ 5 มม./ชม.
- ดัชนีความติด = (รถในภาพ + 1) ÷ (มัธยฐานของกล้อง×ชั่วโมง×ประเภทวัน ตอนฝนไม่ตก + 1) · 1.00 = ปกติ

## ผลหลัก

- วันธรรมดามียอดรถ 07:00 และ 17:00 · วันหยุดยอดเดียวตอนเที่ยง
- ฝนตกเฉพาะบ่ายถึงเย็น และเป็นหย่อม (ชั่วโมงหนักสุดตกแค่ 38% ของสถานี)
- วันธรรมดาที่ฝนตก นับรถได้น้อยลง: ฝนเบา 0.78 (95% CI 0.73–0.82) ฝนหนัก 0.68 (0.63–0.74) · โมเดล mixed-effects: −14% และ −20%
- วันหยุดผลของฝนเล็กและไม่มีนัยสำคัญ
- รถบรรทุกลดลงในชั่วโมงเร่งด่วนวันธรรมดา (~8% เทียบกับ ~10.5% ช่วงกลางวัน)
- กล้องคู่ที่อยู่จุดเดียวกันสอดคล้องกัน (r ≈ 0.60) · พบกล้องที่อาจภาพค้าง 4 ตัว
- ฝนจาก Open-Meteo ผิดเวลาจากสถานีจริง 1–4 ชั่วโมง จึงต้องใช้สถานี กทม.
- สัปดาห์นี้ไม่มีน้ำท่วมถนนจริงรอบกล้อง (สถานีวัดน้ำท่วมถนนใกล้ 76 กล้องวัดได้ 0 ตลอด) · กล้องใกล้จุดน้ำขังที่ยังไม่แก้ ไม่ได้ติดมากกว่าจุดอื่น (p = 0.70) มีแค่ฝนหนักวันหยุดที่เห็นรถน้อยลง 26%

## ข้อจำกัด

ข้อมูล 7 วัน · ไม่มีฝนช่วงเช้า/สาย · ภาพหาย 27 ส.ค. 06–09 น. · YOLO สำเร็จรูปนับได้น้อยลงตอนมืด และนับมอเตอร์ไซค์ขาด · ภาพนิ่งบอกความเร็วไม่ได้ · ผลเป็นความสัมพันธ์ ยังไม่ใช่เหตุและผล · ยังต้องนับมือเพื่อยืนยันว่าผลของฝนไม่ได้มาจากโมเดลนับพลาด

## สมาชิก

_(ใส่ชื่อและรหัสนิสิต)_

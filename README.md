# DSDE Project: ฝนตกกับรถติดในกรุงเทพฯ (Bangkok CCTV Rain & Traffic)

โปรเจกต์วิชา 2110403 Data Science and Data Engineering (DSDE-CEDT) ภาคเรียน 2026/1

**คำถาม:** ฝนตกทำให้จำนวนรถที่กล้อง CCTV ของ กทม. มองเห็นเปลี่ยนไปอย่างไร แยกตามช่วงเวลาของวัน และวันธรรมดากับวันหยุด และทำนายได้ไหม

- วิดีโอนำเสนอ: _(ใส่ลิงก์ YouTube)_
- สไลด์: _(ใส่ลิงก์ PDF)_
- Dashboard: เปิด `dashboard/dashboard.html`
- อินไซต์ 7 ข้อ + ผลโมเดล: `reports/insights.html`
- รายงานคุณภาพข้อมูล: `reports/dq_report.html`

## สถาปัตยกรรม

```
 แหล่งข้อมูล                   Landing            Bronze             Silver              Gold                ผลลัพธ์
 ───────────                  ─────────          ────────           ────────            ──────              ─────────
 cctv_images.zip ─ YOLOv8n ─► (zip เดิม)  ─►  images_index       images (ภาพเสีย/ค้าง)
                                               detections_raw ─►  detections        ─►  fact_images ──────► Dashboard (Plotly + Leaflet)
 cctv_info.csv ─────────────────────────────►  cameras        ─►  cameras            features_cam_hr ──► Spark ML ─► MLflow
 s1 ฝน กทม. (ฟอร์ม) ──────►  HTML 112 หน้า ─►  bma_rain       ─►  rain_hourly        camera_profile ───► สถิติ ─► อินไซต์ 7 ข้อ
 s2 METAR  s3 Open-Meteo ──►  CSV / JSON   ─►  metar, openmeteo ─► metar, openmeteo
 s4 ดวงอาทิตย์ s5 วันหยุด ─►  JSON / HTML  ─►  sun, holidays  ─►  calendar
 s6 OpenStreetMap ────────►  JSON         ─►  osm_poi/roads  ─►  osm_* ──┐
 s8 น้ำท่วมถนน (ฟอร์ม) ───►  HTML 105 หน้า ─►  bma_flood      ─►  flood_* ─┼─► GeoPandas (EPSG:32647) buffer/sjoin, KDE, DBSCAN ─► camera_spatial
 s9 BMA Open Data (CKAN) ─►  CSV          ─►  bma_flood_risk ─►  flood_risk_* ┘
                          requests+BS4      pandas→Parquet      PySpark             Spark SQL

 Streaming demo: kafka_producer ─► Kafka topic cctv-frames (3 partitions) ─► Spark Structured Streaming (หน้าต่าง 10 นาที) ─► bronze/stream_counts_10min
 Orchestration: Prefect flow  extract → bronze → detect → silver → spatial → gold → train(+explain) → analysis → reports
```

## โครงสร้างโฟลเดอร์

| โฟลเดอร์ | หน้าที่ | ส่วนตามเกณฑ์ |
|---|---|---|
| `configs/settings.yaml` | ค่าทั้งหมด: path, เกณฑ์ฝน, รัศมี, วันแบ่ง train/test | – |
| `src/extract/` | s1–s9 ดึงข้อมูลเก็บไฟล์ดิบลง `lake/landing/` + `_manifest.csv` (ตรวจ robots.txt, retry, หน่วงเวลา) | Web scraping (งานบังคับ) |
| `src/ingest/` | `bronze_ingest.py` แปลงไฟล์ดิบเป็น Parquet (ทุกคอลัมน์เป็น string) · `kafka_producer.py`, `stream_counts.py` | Data Engineering |
| `src/detect/` | `yolo_detect.py` เก็บกรอบรถทุกกล่อง + dHash + ความสว่าง · `label_sample.py` เครื่องมือนับมือ 200 ภาพ | Data Engineering |
| `src/clean/` | `silver_clean.py` 38 กฎทำความสะอาดด้วย PySpark บันทึกทุกกฎลง `reports/dq_rules.json` | Data Engineering |
| `src/spatial/` | `geo_features.py` GeoPandas, KDE, DBSCAN | Data Science |
| `src/gold/` | `build_gold.py` Spark SQL สร้าง fact/feature/profile | Data Engineering |
| `src/ml/` | `train_spark.py` Spark ML Pipeline + MLflow · `explain.py` · `analysis.py` สถิติ 7 อินไซต์ | Data Science |
| `src/viz/` | กราฟ, dashboard, รายงาน, notebook | BI Dashboard / Insights |
| `flows/pipeline_flow.py` | Prefect `@flow` / `@task` รันทั้งหมด | Workflow management |
| `lake/` | `landing/` (ไม่ขึ้น git) · `bronze/` · `silver/` · `gold/` | Medallion layers |
| `notebooks/` | 01 Data Engineering · 02 Analysis · 03 Modeling (รันแล้วพร้อมผลลัพธ์) | – |
| `dashboard/`, `reports/` | ผลลัพธ์ HTML + รูป | BI Dashboard / Insights |

## ข้อมูล

| # | แหล่ง | วิธีดึง | ใช้ทำอะไร |
|---|---|---|---|
| – | ภาพ CCTV 100 กล้อง 61,319 ภาพ 25–31 ส.ค. 2569 + `cctv_info.csv` | ข้อมูลจากอาจารย์ | นับรถ YOLOv8n, พิกัดกล้อง |
| s1 | สถานีวัดฝน สำนักการระบายน้ำ กทม. (123 สถานี) | ส่งฟอร์ม POST + BeautifulSoup 112 หน้า | ฝนรายชั่วโมงใกล้กล้อง |
| s2 | METAR ดอนเมือง/สุวรรณภูมิ (Iowa Mesonet) | API (CSV) | ยืนยันช่วงฝน/พายุ |
| s3 | Open-Meteo Historical | API (JSON) | เทียบฝนจากโมเดลอากาศ, เมฆ |
| s4 | sunrise-sunset.org | API (JSON) | แบ่งช่วงแสง กลางวัน/โพล้เพล้/กลางคืน |
| s5 | timeanddate.com วันหยุดไทย 2026 | HTML + BeautifulSoup | ยืนยันวันหยุดราชการ |
| s6 | OpenStreetMap Overpass | API (JSON) | ชนิดถนน, สถานที่ 9 ประเภทรอบกล้อง |
| s8 | สถานีวัดน้ำท่วมถนน กทม. | ส่งฟอร์ม POST + BeautifulSoup 105 หน้า | น้ำท่วมถนนรอบกล้องรายชั่วโมง |
| s9 | BMA Open Data (CKAN) จุดเสี่ยงน้ำท่วม 737 จุด, ปี 2568, สถิติ 2566 | API (CKAN) | สถานะการแก้ไขจุดเสี่ยง, KDE, DBSCAN |

## การทำความสะอาดที่สำคัญ (ดูทั้งหมดใน `reports/dq_report.html`)

- ภาพเสีย (< 3 KB หรือเปิดไม่ได้) 504 ภาพ
- **ภาพค้าง** 580 ภาพ: ภาพที่ไฟล์ขนาดเท่ากันและ dHash เท่ากันกับภาพก่อนหน้าของกล้องเดียวกัน (กล้อง 206, 150, 938, 939, 395, 432, 1804, 188) · ลองใช้ dHash ใกล้เคียง (≤ 2 bit) ก่อนแล้วพบว่าจับผิดในกล้องที่ฉากนิ่ง จึงเปลี่ยนเป็นภาพซ้ำแบบตรงทุกไบต์
- **เว็บฝน กทม. แสดงเฉพาะ 51 สถานีที่ฝนมากที่สุดในแต่ละชั่วโมง** (เรียงจากมากไปน้อย) สถานีที่ไม่แสดงจึงไม่ใช่ข้อมูลหาย: ถ้าแถวสุดท้ายเป็น 0 → แทนเป็น 0 (7,992 ค่า) ถ้าไม่ใช่ → censored (72 ค่า)
- ปี พ.ศ. → ค.ศ., เวลา UTC → เวลาไทย, ไฟล์ cp874, สถานะจุดเสี่ยง 1/2/3 → ยังไม่แก้ 4 → แก้บางส่วน 5 → แก้แล้ว
- ตัด IP address ของกล้องและเซนเซอร์ออกตั้งแต่ขั้น Bronze

## โมเดล (Spark ML)

- **Label:** รถเฉลี่ยต่อภาพของกล้อง×ชั่วโมง (เทรนบน log1p) · 10,125 แถว
- **แบ่งตามเวลา:** train 25–29 ส.ค. / test 30–31 ส.ค. · จูนแบบ forward-chaining (≤27 → 28, ≤28 → 29) ไม่ใช้ CrossValidator แบบสุ่มเพราะข้อมูลอนาคตจะรั่วเข้าการเทรน
- **Pipeline:** Imputer → StringIndexer → (OneHotEncoder) → VectorAssembler → LinearRegression / RandomForest / GBT
- **Feature `hist_profile`:** ค่าเฉลี่ยของกล้อง×ชั่วโมง×ประเภทวันจากข้อมูลเทรนเท่านั้น (แถวเทรนใช้แบบ leave-one-day-out)
- **กันข้อมูลรั่ว:** ไม่ใช้ฝนชั่วโมงเดียวกัน (รายงานหลังจบชั่วโมง) ใช้ฝนชั่วโมงก่อนหน้าแทน · ไม่ใช้ความสว่างภาพ, occupancy, ดัชนีความหนาแน่น
- **Ablation:** F0 ประวัติ → F1 +ปฏิทิน/แสง → F2 +อากาศ → F3 +พื้นที่/น้ำท่วม → F4 +จำนวนรถชั่วโมงก่อน (nowcast)

| โมเดล | MAE (คัน/ภาพ) | R² |
|---|---|---|
| baseline ค่าเฉลี่ยประวัติ | 1.207 | 0.714 |
| baseline ชั่วโมงก่อนหน้า | 1.349 | 0.655 |
| **Linear F3 (เลือกด้วย CV)** | **1.141** | **0.748** |
| Random Forest F3 | 1.107 | 0.763 |
| Random Forest F4 nowcast | 1.030 | 0.802 |

ในชั่วโมงที่ฝนตก ข้อมูลอากาศที่ scrape มาลด MAE ได้ 17% (ฝนเบา) และ 20% (ฝนหนัก) เทียบกับ baseline

## ผลหลัก (รายละเอียดใน `reports/insights.html`)

1. วันธรรมดายอด 07:00 และ 17:00 · วันหยุดยอดเดียว 12:00 และน้อยกว่า 20%
2. ตอนเย็นหนาแน่นกว่าตอนเช้า (50 กล้อง vs 23) · สมมติฐานเรื่องสถานีรถไฟฟ้าไม่ได้รับการยืนยัน
3. ฝนตกวันธรรมดา รถลด 22% (ฝนเบา) ถึง 30% (ฝนหนัก) แม้ตอนกลางวัน · ยืนยันด้วย METAR · Open-Meteo ใช้แทนสถานีจริงไม่ได้
4. ฝนวันหยุดแทบไม่มีผล · ไม่พบน้ำท่วมถนนรอบกล้องทั้งสัปดาห์ · จุดเสี่ยงที่ยังไม่แก้ไม่ได้ติดกว่า
5. วันหยุดคึกหน้าวัด/สวนจตุจักร (+15%) เงียบในย่านธุรกิจนราธิวาสฯ (−68%) · กล้องใกล้สถานีรถไฟฟ้าวันหยุดคึกกว่า (ρ = 0.25)
6. บางกอกใหญ่/ราชเทวี/ธนบุรีหนาแน่นสุด · สัมพันธวงศ์/พระนคร/ดุสิตน้อยสุด · เย็นวันศุกร์หนักสุด
7. รถบรรทุกมากบนทางด่วน รถบัสบนถนนหลัก มอเตอร์ไซค์ในย่านร้านอาหาร · รถบรรทุกลดลงชั่วโมงเร่งด่วนวันธรรมดา

## วิธีรัน

```bash
python3.12 -m venv .venv && .venv/bin/pip install -r requirements.txt   # ต้องมี Java 17 (brew install openjdk@17)

.venv/bin/python flows/pipeline_flow.py                               # ทั้งหมด (ต้องมี ~/Downloads/cctv_images.zip)
.venv/bin/python flows/pipeline_flow.py --skip-extract --skip-detect  # เริ่มจาก Bronze ที่อยู่ใน repo ไม่ต้องมีภาพ

python -m src.extract.run_extract bma_rain        # ดึงเฉพาะแหล่งเดียว
python -m src.detect.label_sample                 # สร้าง reports/label_tool.html สำหรับนับมือ 200 ภาพ
python -m src.detect.label_sample --score manual_counts.csv   # วัดความแม่นของ YOLO
mlflow ui --backend-store-uri sqlite:///models/mlflow.db        # ดูทุก run

docker compose -f docker/kafka-compose.yml up -d                # เดโม streaming
python -m src.ingest.kafka_producer --limit 3000
python -m src.ingest.stream_counts 60
```

## ข้อจำกัด

ข้อมูล 7 วัน · ไม่มีฝนช่วงเช้า · ภาพหาย 27 ส.ค. 06–09 น. · YOLO สำเร็จรูปนับได้น้อยลงตอนมืดและนับมอเตอร์ไซค์ขาด (ยังต้องนับมือยืนยัน) · สถานีฝนอยู่ห่างกล้องเฉลี่ย 850 ม. · โมเดลทำนายกล้องที่ไม่เคยเห็นไม่ได้ · ผลเป็นความสัมพันธ์ ไม่ใช่เหตุและผล

## สมาชิก

_(ใส่ชื่อและรหัสนิสิต)_

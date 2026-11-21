import os
import subprocess
import sys

import nbformat as nbf

from src.common.config import ROOT

SETUP = """import os, sys, json
ROOT = os.path.abspath('..')
sys.path.insert(0, ROOT)
os.chdir(ROOT)
import pandas as pd
pd.set_option('display.max_columns', 40, 'display.width', 200)
from IPython.display import Image, display"""

NOTEBOOKS = {
    '01_data_engineering.ipynb': [
        ('md', '# 1 · Data Engineering: Landing → Bronze → Silver → Gold\n\n'
               '| ชั้น | เก็บอะไร | เครื่องมือ |\n|---|---|---|\n'
               '| Landing | ไฟล์ดิบตามที่ดึงมา (HTML / JSON / CSV) + `_manifest.csv` | requests + BeautifulSoup |\n'
               '| Bronze | แปลงเป็นตาราง Parquet แต่ทุกคอลัมน์ยังเป็น string ไม่แก้ค่า | pandas → Parquet |\n'
               '| Silver | แปลงชนิดข้อมูล ทำความสะอาด ทำเครื่องหมายแถวที่มีปัญหา | PySpark |\n'
               '| Gold | ตาราง fact / feature / profile พร้อมทำ dashboard และ ML | Spark SQL |'),
        ('code', SETUP),
        ('md', '## Extraction log (ทุกคำขอที่ scrape)'),
        ('code', "m = pd.read_csv('lake/landing/_manifest.csv') if os.path.exists('lake/landing/_manifest.csv') else pd.DataFrame()\n"
                 "m.groupby(['source', 'status']).size().unstack(fill_value=0) if len(m) else 'manifest not present (landing/ is gitignored)'"),
        ('md', '## Bronze: ตารางดิบ'),
        ('code', "import glob\nfor p in sorted(glob.glob('lake/bronze/*.parquet')):\n    df = pd.read_parquet(p)\n    print(f'{os.path.basename(p):32s} rows={len(df):>7,} cols={df.shape[1]}')"),
        ('md', '## Silver: Spark DataFrame + schema'),
        ('code', "from src.common.spark import spark\ns = spark()\nimg = s.read.parquet('lake/silver/images.parquet')\nimg.printSchema()\n"
                 "img.groupBy('is_broken', 'is_frozen', 'is_valid').count().orderBy('count', ascending=False).show()"),
        ('md', '## Data quality rules (ทุกกฎและจำนวนแถวที่โดน)'),
        ('code', "pd.DataFrame(json.load(open('reports/dq_rules.json')))"),
        ('code', "display(Image('reports/figures/dq_image_funnel.png'))"),
        ('md', '## Gold: Spark SQL'),
        ('code', "s.read.parquet('lake/gold/fact_images').createOrReplaceTempView('fact_images')\n"
                 "s.sql('''select day_type, rain_level, count(*) as images, round(avg(vehicles),2) as veh_mean\n"
                 "         from fact_images group by day_type, rain_level order by day_type, rain_level''').show()"),
        ('code', "feat = pd.read_parquet('lake/gold/features_cam_hr.parquet')\nprint(feat.shape)\nfeat.head()"),
    ],
    '02_analysis_insights.ipynb': [
        ('md', '# 2 · Data Science: สถิติและอินไซต์ 7 ข้อ\n\nตัวเลขทั้งหมดมาจาก `src/ml/analysis.py` (อ่าน Gold layer) และเก็บใน `reports/analysis.json`'),
        ('code', SETUP),
        ('code', "a = json.load(open('reports/analysis.json'))\n{k: a[k] for k in ['images_analysed', 'vehicles_counted', 'cameras']}"),
        ('md', '## อินไซต์ 1 · จังหวะรายชั่วโมง'),
        ('code', "display(Image('reports/figures/i1_hourly_profile.png'))\n{k: v for k, v in a['i1'].items() if k != 'hourly_profile'}"),
        ('md', '## อินไซต์ 2 · เย็น > เช้า, ใกล้รถไฟฟ้า'),
        ('code', "display(Image('reports/figures/i2_am_pm_rail.png'))\na['i2']"),
        ('md', '## อินไซต์ 3 · ฝนวันธรรมดา'),
        ('code', "display(Image('reports/figures/i3_i4_rain_effect.png'))\n{k: v for k, v in a['i3'].items() if k != 'rain_by_date_hour'}"),
        ('md', '## อินไซต์ 4 · ฝนวันหยุด + น้ำท่วม'),
        ('code', 'a["i4"]'),
        ('md', '## อินไซต์ 5 · วันหยุดตามสถานที่'),
        ('code', "display(Image('reports/figures/i5_weekend_ratio.png'))\na['i5']"),
        ('md', '## อินไซต์ 6 · เขต / ชนิดถนน / วันศุกร์'),
        ('code', "display(Image('reports/figures/i6_district.png'))\na['i6']"),
        ('md', '## อินไซต์ 7 · ประเภทรถ'),
        ('code', "display(Image('reports/figures/i7_vehicle_mix.png'))\ndisplay(Image('reports/figures/i7_truck_by_hour.png'))\na['i7']"),
    ],
    '03_modeling.ipynb': [
        ('md', '# 3 · Machine Learning (Spark ML)\n\n'
               '- **Label**: รถเฉลี่ยต่อภาพของกล้อง×ชั่วโมง (เทรนบน log1p)\n'
               '- **Split ตามเวลา**: train 25–29 ส.ค. · test 30–31 ส.ค. (ห้ามสุ่ม)\n'
               '- **Tuning**: forward-chaining (train ≤27 → valid 28, train ≤28 → valid 29) × ParamGridBuilder-style grid\n'
               '- **Pipeline**: StringIndexer → (OneHotEncoder) → VectorAssembler → LinearRegression / RandomForest / GBT\n'
               '- **Leakage guard**: ไม่ใช้ ฝนชั่วโมงเดียวกัน, ความสว่างภาพ, occupancy, ดัชนีความหนาแน่น'),
        ('code', SETUP),
        ('code', "m = json.load(open('reports/model_report.json'))\nm['rows'], m['split']"),
        ('code', "pd.DataFrame(m['runs'])[['model','features','params','cv_mae','mae','rmse','r2']].sort_values('mae')"),
        ('code', "display(Image('reports/figures/ml_model_comparison.png'))\ndisplay(Image('reports/figures/ml_actual_vs_pred.png'))"),
        ('code', "display(Image('reports/figures/ml_feature_importance.png'))\npd.DataFrame(m['best']['by_group']).T"),
        ('md', '## โมเดลบอกว่าฝนลดรถเท่าไร (counterfactual) และทำนายกล้องที่ไม่เคยเห็น'),
        ('code', "m['rain_effect'], m['camera_holdout']"),
        ('md', '## โหลด PipelineModel ที่บันทึกไว้แล้วใช้ทำนาย'),
        ('code', "from pyspark.ml import PipelineModel\nfrom pyspark.sql import functions as F\nfrom src.ml.train_spark import prepare, split, M\n"
                 "df = prepare()\ntrain, test = split(df, M['train_end'], F.col('date') >= str(M['test_start']))\n"
                 "model = PipelineModel.load('models/best_pipeline_model')\n"
                 "(model.transform(test.where(\"date = '2026-08-31' and hour = 17\"))\n"
                 " .selectExpr('cam', 'rain_prev_level', 'round(veh_mean,2) as actual', 'round(expm1(hist_profile),2) as baseline', 'round(expm1(prediction),2) as predicted')\n"
                 " .orderBy('cam').show(12))"),
        ('md', '## MLflow\n\n`mlflow ui --backend-store-uri sqlite:///models/mlflow.db` แล้วเปิด http://127.0.0.1:5000 เพื่อดูทุก run'),
    ],
}


def main(execute=True):
    out_dir = os.path.join(ROOT, 'notebooks')
    for name, cells in NOTEBOOKS.items():
        nb = nbf.v4.new_notebook()
        nb.cells = [nbf.v4.new_markdown_cell(c) if t == 'md' else nbf.v4.new_code_cell(c) for t, c in cells]
        p = os.path.join(out_dir, name)
        nbf.write(nb, p)
        if execute:
            subprocess.run([sys.executable, '-m', 'jupyter', 'nbconvert', '--to', 'notebook', '--execute', '--inplace',
                            '--ExecutePreprocessor.timeout=900', p], check=True, cwd=out_dir)
        print('notebook', name)


if __name__ == '__main__':
    main('--no-exec' not in sys.argv)

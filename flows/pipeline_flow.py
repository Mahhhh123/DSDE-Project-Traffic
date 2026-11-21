import os
import sys

os.environ.setdefault('PREFECT_SERVER_ANALYTICS_ENABLED', 'false')
os.environ.setdefault('MLFLOW_DISABLE_AGENT_HINT', '1')

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prefect import flow, task

from src.extract import run_extract


@task(retries=2, retry_delay_seconds=30, tags=['extract'])
def extract(source):
    run_extract.SOURCES[source].main()
    return source


@task(tags=['ingest'])
def ingest_bronze(_sources):
    from src.ingest import bronze_ingest
    bronze_ingest.main()


@task(tags=['detect'])
def detect_vehicles(_bronze):
    from src.detect import yolo_detect
    yolo_detect.main()


@task(tags=['clean'])
def clean_silver(_bronze, _detect):
    from src.clean import silver_clean
    silver_clean.main()


@task(tags=['spatial'])
def spatial_features(_silver):
    from src.spatial import geo_features
    geo_features.main()


@task(tags=['gold'])
def build_gold(_spatial):
    from src.gold import build_gold
    build_gold.main()


@task(tags=['ml'])
def train_models(_gold):
    from src.ml import explain, train_spark
    train_spark.main()
    explain.main()


@task(tags=['analysis'])
def analyse(_gold):
    from src.ml import analysis
    analysis.main()


@task(tags=['report'])
def publish(_model, _analysis):
    from src.viz import reports
    reports.main()


@flow(name='bangkok-cctv-rain-traffic', log_prints=True)
def pipeline(skip_extract: bool = False, skip_detect: bool = False):
    sources = [] if skip_extract else [extract(s) for s in run_extract.SOURCES]
    bronze = ingest_bronze(sources)
    det = None if skip_detect else detect_vehicles(bronze)
    silver = clean_silver(bronze, det)
    spatial = spatial_features(silver)
    gold = build_gold(spatial)
    model = train_models(gold)
    ana = analyse(gold)
    publish(model, ana)


if __name__ == '__main__':
    pipeline(skip_extract='--skip-extract' in sys.argv, skip_detect='--skip-detect' in sys.argv)

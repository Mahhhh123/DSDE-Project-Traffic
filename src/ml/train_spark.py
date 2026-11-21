import itertools
import json
import random
import time

import mlflow
from pyspark.ml import Pipeline
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml.feature import Imputer, OneHotEncoder, StringIndexer, VectorAssembler
from pyspark.ml.regression import GBTRegressor, LinearRegression, RandomForestRegressor
from pyspark.sql import Window
from pyspark.sql import functions as F

from src.common.config import CFG, path, write_json
from src.common.spark import read, spark

M = CFG['model']
LABEL = 'label'
KEYS = [['cam', 'hour', 'is_weekend'], ['cam', 'hour'], ['cam']]

HIST = ['hist_profile', 'hour', 'dow', 'is_weekend']
CAL_C, CAL_N = ['light'], ['is_holiday']
WX_C, WX_N = ['rain_prev_level'], ['rain_prev_mm', 'city_rain_share_prev', 'metar_rain_prev', 'om_precip_prev', 'om_cloud_prev']
LOC_C = ['highway', 'district']
LOC_N = ['lanes_n', 'poi_mall', 'poi_market', 'poi_government', 'poi_office', 'poi_school', 'poi_rail_station', 'poi_bus_stop', 'poi_food',
         'poi_hospital', 'dist_rail_m', 'flood_points_500m', 'flood_unfixed_500m', 'flood_kde', 'in_flood_hotspot', 'flood_risk2568_500m',
         'flood_events_2566_district']
LAG_N = ['lag1_label', 'lag1_missing']

FEATURE_SETS = {
    'F0_history': ([], HIST),
    'F1_+calendar': (CAL_C, HIST + CAL_N),
    'F2_+weather': (CAL_C + WX_C, HIST + CAL_N + WX_N),
    'F3_+location': (CAL_C + WX_C + LOC_C, HIST + CAL_N + WX_N + LOC_N),
    'F4_+lag1(nowcast)': (CAL_C + WX_C + LOC_C, HIST + CAL_N + WX_N + LOC_N + LAG_N),
}
UNSEEN_CAM_SETS = {
    'time+weather': (CAL_C + WX_C, ['hour', 'dow', 'is_weekend'] + CAL_N + WX_N),
    'time+weather+location': (CAL_C + WX_C + LOC_C, ['hour', 'dow', 'is_weekend'] + CAL_N + WX_N + LOC_N),
}

GRIDS = {
    'linear': (lambda: LinearRegression(featuresCol='features', labelCol=LABEL, maxIter=100),
               {'regParam': [0.0, 0.01, 0.1], 'elasticNetParam': [0.0, 0.5]}),
    'random_forest': (lambda: RandomForestRegressor(featuresCol='features', labelCol=LABEL, numTrees=150, maxBins=64, seed=M['seed']),
                      {'maxDepth': [8, 12], 'minInstancesPerNode': [1, 5]}),
    'gbt': (lambda: GBTRegressor(featuresCol='features', labelCol=LABEL, maxIter=150, maxBins=64, seed=M['seed']),
            {'maxDepth': [3, 5], 'stepSize': [0.05, 0.1]}),
}


def add_history(train, other):
    out = other
    for i, k in enumerate(KEYS):
        out = out.join(train.groupBy(k).agg(F.mean(LABEL).alias('h%d' % i)), k, 'left')
    gm = train.agg(F.mean(LABEL)).first()[0]
    return out.withColumn('hist_profile', F.coalesce('h0', 'h1', 'h2', F.lit(gm))).drop('h0', 'h1', 'h2')


def add_history_oof(train):
    out = train
    for i, k in enumerate(KEYS):
        tot = train.groupBy(k).agg(F.sum(LABEL).alias('s'), F.count('*').alias('n'))
        day = train.groupBy(k + ['date']).agg(F.sum(LABEL).alias('sd'), F.count('*').alias('nd'))
        oof = day.join(tot, k).select(*k, 'date', F.when(F.col('n') > F.col('nd'), (F.col('s') - F.col('sd')) / (F.col('n') - F.col('nd'))).alias('h%d' % i))
        out = out.join(oof, k + ['date'], 'left')
    gm = train.agg(F.mean(LABEL)).first()[0]
    return out.withColumn('hist_profile', F.coalesce('h0', 'h1', 'h2', F.lit(gm))).drop('h0', 'h1', 'h2')


def split(df, train_end, test_filter):
    tr = df.filter(F.col('date') <= str(train_end))
    te = df.filter(test_filter)
    return add_history_oof(tr).cache(), add_history(tr, te).cache()


def build(cats, nums, estimator, linear):
    imp = [Imputer(inputCols=nums, outputCols=[n + '_i' for n in nums], strategy='median')]
    idx = [StringIndexer(inputCol=c, outputCol=c + '_idx', handleInvalid='keep') for c in cats]
    ohe = [OneHotEncoder(inputCols=[c + '_idx' for c in cats], outputCols=[c + '_ohe' for c in cats], handleInvalid='keep')] if linear and cats else []
    inputs = [c + ('_ohe' if linear else '_idx') for c in cats] + [n + '_i' for n in nums]
    va = VectorAssembler(inputCols=inputs, outputCol='features')
    return Pipeline(stages=imp + idx + ohe + [va, estimator])


def metrics(pred, col='prediction'):
    p = pred.withColumn('y', F.expm1(LABEL)).withColumn('yhat', F.greatest(F.expm1(col), F.lit(0.0)))
    return {m: round(RegressionEvaluator(labelCol='y', predictionCol='yhat', metricName=m).evaluate(p), 4) for m in ['mae', 'rmse', 'r2']}


def grid(params):
    return [dict(zip(params, v)) for v in itertools.product(*params.values())]


def fit(df, cats, nums, kind, params):
    est = GRIDS[kind][0]()
    for k, v in params.items():
        est = est.copy({est.getParam(k): v})
    return build(cats, nums, est, kind == 'linear').fit(df)


def tune(folds, cats, nums, kind):
    best = None
    for params in grid(GRIDS[kind][1]):
        mae = sum(metrics(fit(tr, cats, nums, kind, params).transform(va))['mae'] for tr, va in folds) / len(folds)
        if best is None or mae < best[1]:
            best = (params, mae)
    return best


def importances(model, cats, nums):
    last = model.stages[-1]
    if not hasattr(last, 'featureImportances'):
        return {}
    return dict(sorted(((n, round(float(v), 4)) for n, v in zip(cats + nums, last.featureImportances.toArray())), key=lambda x: -x[1]))


def prepare():
    spark()
    w = Window.partitionBy('cam', 'date').orderBy('hour')
    df = (read('gold', 'features_cam_hr.parquet')
          .filter(F.col('n_images') >= M['min_images_per_hour'])
          .withColumn(LABEL, F.log1p('veh_mean'))
          .withColumn('date', F.col('date').cast('string')))
    prev = F.lag(LABEL).over(w)
    prev_hour = F.lag('hour').over(w)
    df = (df.withColumn('lag1_label', F.when(prev_hour == F.col('hour') - 1, prev))
            .withColumn('lag1_missing', F.col('lag1_label').isNull().cast('int')))
    num_cols = set(HIST + CAL_N + WX_N + LOC_N + LAG_N) - {'hist_profile'}
    for c in num_cols:
        df = df.withColumn(c, F.col(c).cast('double'))
    return df.cache()


def group_metrics(pred):
    out = {}
    for col in ['is_weekend', 'rain_prev_level', 'light']:
        for v in sorted(r[0] for r in pred.select(col).distinct().collect()):
            sub = pred.filter(F.col(col) == v)
            n = sub.count()
            if n >= 20:
                out['%s=%s' % (col, v)] = {'n': n, 'model': metrics(sub), 'baseline': metrics(sub, 'hist_profile')}
    return out


def rain_counterfactual(model, test):
    wet = test.filter(F.col('rain_prev_mm') >= CFG['rain']['dry_below_mm'])
    if wet.count() == 0:
        return {}
    dry = (wet.withColumn('rain_prev_mm', F.lit(0.0)).withColumn('rain_prev_level', F.lit('dry'))
           .withColumn('city_rain_share_prev', F.lit(0.0)).withColumn('metar_rain_prev', F.lit(0.0)).withColumn('om_precip_prev', F.lit(0.0)))
    a = model.transform(wet).select('cam', 'date', 'hour', 'is_weekend', F.expm1('prediction').alias('p_rain'), F.expm1(LABEL).alias('actual'))
    b = model.transform(dry).select('cam', 'date', 'hour', F.expm1('prediction').alias('p_dry'))
    rows = (a.join(b, ['cam', 'date', 'hour']).groupBy('is_weekend')
            .agg(F.count('*').alias('n'), F.mean('actual').alias('actual'), F.mean('p_rain').alias('p_rain'), F.mean('p_dry').alias('p_dry')).collect())
    return {('weekend' if r['is_weekend'] else 'weekday'): {'n': r['n'], 'actual': round(r['actual'], 3), 'pred_with_rain': round(r['p_rain'], 3),
                                                            'pred_if_dry': round(r['p_dry'], 3), 'ratio': round(r['p_rain'] / r['p_dry'], 3)} for r in rows}


def unseen_cameras(df, kind, params):
    cams = sorted(r[0] for r in df.select('cam').distinct().collect())
    random.Random(M['seed']).shuffle(cams)
    k = M['camera_folds']
    res = {}
    for name, (cats, nums) in UNSEEN_CAM_SETS.items():
        scores = []
        for i in range(k):
            hold = cams[i::k]
            tr, te = df.filter(~F.col('cam').isin(hold)), df.filter(F.col('cam').isin(hold))
            scores.append(metrics(fit(tr, cats, nums, kind, params).transform(te)))
        res[name] = {m: round(sum(s[m] for s in scores) / k, 4) for m in ['mae', 'rmse', 'r2']}
    return res


def main():
    mlflow.set_tracking_uri('sqlite:///' + path('models', 'mlflow.db'))
    mlflow.set_experiment('cctv-traffic-forecast')
    df = prepare()
    folds = [split(df, f['train_end'], F.col('date') == str(f['valid'])) for f in M['tuning_folds']]
    train, test = split(df, M['train_end'], F.col('date') >= str(M['test_start']))
    report = {'rows': {'all': df.count(), 'train': train.count(), 'test': test.count()},
              'split': {'train': '%s..%s' % (CFG['period']['start'], M['train_end']), 'test': '%s..%s' % (M['test_start'], CFG['period']['end']),
                        'tuning_folds': [{k: str(v) for k, v in f.items()} for f in M['tuning_folds']]},
              'runs': []}
    print(report['rows'], flush=True)

    for name, col in [('baseline_history_profile', 'hist_profile'), ('baseline_persistence_lag1', 'lag1_label')]:
        sub = test if col == 'hist_profile' else test.filter(F.col('lag1_label').isNotNull())
        m = metrics(sub, col)
        with mlflow.start_run(run_name=name):
            mlflow.log_params({'model': name})
            mlflow.log_metrics(m)
        report['runs'].append({'model': name, 'features': col, 'params': {}, 'cv_mae': None, **m, 'n_test': sub.count()})
        print(name, m, flush=True)

    best = None
    for fs, (cats, nums) in FEATURE_SETS.items():
        for kind in GRIDS:
            if kind == 'random_forest' and fs not in ('F3_+location', 'F4_+lag1(nowcast)'):
                continue
            t0 = time.time()
            params, cv_mae = tune(folds, cats, nums, kind)
            model = fit(train, cats, nums, kind, params)
            m = metrics(model.transform(test))
            run = {'model': kind, 'features': fs, 'params': params, 'cv_mae': round(cv_mae, 4), **m, 'seconds': round(time.time() - t0)}
            with mlflow.start_run(run_name='%s_%s' % (kind, fs)):
                mlflow.log_params({'model': kind, 'features': fs, **params})
                mlflow.log_metrics({'cv_mae': cv_mae, **m})
            report['runs'].append(run)
            print(run, flush=True)
            if fs != 'F4_+lag1(nowcast)' and (best is None or cv_mae < best[0]):
                best = (cv_mae, fs, kind, params, model)
            if fs == 'F4_+lag1(nowcast)' and kind == 'gbt':
                report['nowcast'] = run

    _, fs, kind, params, model = best
    cats, nums = FEATURE_SETS[fs]
    model.write().overwrite().save(path('models', 'best_pipeline_model'))
    pred = model.transform(test).cache()
    report['best'] = {'model': kind, 'features': fs, 'params': params, 'test': metrics(pred), 'importance': importances(model, cats, nums),
                      'by_group': group_metrics(pred), 'selection': 'lowest forward-chaining CV MAE among F0–F3 (planning model, no lag)'}
    report['rain_effect'] = rain_counterfactual(model, test)
    gkind, gparams = 'gbt', next(r['params'] for r in report['runs'] if r['model'] == 'gbt' and r['features'] == 'F3_+location')
    report['camera_holdout'] = unseen_cameras(df, gkind, gparams)
    (pred.withColumn('y', F.expm1(LABEL)).withColumn('yhat', F.greatest(F.expm1('prediction'), F.lit(0.0)))
     .withColumn('baseline', F.expm1('hist_profile'))
     .select('cam', 'date', 'hour', 'is_weekend', 'rain_prev_level', 'light', 'district', 'highway', 'y', 'yhat', 'baseline')
     .toPandas().to_parquet(path('gold', 'model_predictions_test.parquet'), index=False))
    write_json(report, 'model_report.json')
    print(json.dumps({k: report[k] for k in ['best', 'rain_effect', 'camera_holdout']}, ensure_ascii=False, indent=1), flush=True)


if __name__ == '__main__':
    main()
    spark().stop()

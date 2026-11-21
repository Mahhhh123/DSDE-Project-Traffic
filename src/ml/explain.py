import json

from pyspark.ml import PipelineModel
from pyspark.sql import functions as F

from src.common.config import CFG, path, read_json, write_json
from src.common.spark import spark
from src.ml.train_spark import FEATURE_SETS, M, fit, importances, prepare, split


def vector_names(model, df):
    out = model.transform(df.limit(5))
    meta = out.schema['features'].metadata['ml_attr']['attrs']
    names = {}
    for group in meta.values():
        for a in group:
            names[a['idx']] = a['name']
    return [names[i] for i in range(len(names))]


def main():
    spark()
    rep = read_json('model_report.json')
    df = prepare()
    train, test = split(df, M['train_end'], F.col('date') >= str(M['test_start']))
    best = PipelineModel.load(path('models', 'best_pipeline_model'))
    last = best.stages[-1]
    if hasattr(last, 'coefficients'):
        names = vector_names(best, test)
        coefs = sorted(zip(names, last.coefficients.toArray()), key=lambda x: -abs(x[1]))
        rep['best']['coefficients_log_scale'] = {n: round(float(c), 4) for n, c in coefs if abs(c) > 1e-6}
        rep['best']['weather_coefficients_pct'] = {n: round((2.718281828 ** float(c) - 1) * 100, 1) for n, c in coefs
                                                   if any(k in n for k in ['rain', 'metar', 'om_'])}
    rf = next(r for r in rep['runs'] if r['model'] == 'random_forest' and r['features'] == 'F3_+location')
    cats, nums = FEATURE_SETS['F3_+location']
    rf_model = fit(train, cats, nums, 'random_forest', rf['params'])
    rep['rf_importance_F3'] = importances(rf_model, cats, nums)
    write_json(rep, 'model_report.json')
    print(json.dumps({k: rep['best'].get(k) for k in ['weather_coefficients_pct']}, ensure_ascii=False, indent=1))
    print(list(rep['rf_importance_F3'].items())[:12])


if __name__ == '__main__':
    main()

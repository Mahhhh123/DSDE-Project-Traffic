import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from src.common.config import CFG, path, write_json

warnings.filterwarnings('ignore')
RNG = np.random.default_rng(CFG['model']['seed'])
DAY = {0: 'weekday', 1: 'weekend'}


def load():
    f = pd.read_parquet(path('gold', 'fact_images'))
    f['date'] = f['date'].astype(str)
    f = f[f['count_outlier'] == 0]
    prof = pd.read_parquet(path('gold', 'camera_profile.parquet'))
    return f, prof


def gmean_ratio(x):
    return float(np.exp(np.log(x).mean()))


def cluster_boot(df, value, group='cam', reps=1000, fn=gmean_ratio):
    cams = df[group].unique()
    by = {c: g[value].to_numpy() for c, g in df.groupby(group)}
    est = fn(df[value].to_numpy())
    boots = []
    for _ in range(reps):
        pick = RNG.choice(cams, len(cams), replace=True)
        boots.append(fn(np.concatenate([by[c] for c in pick])))
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {'estimate': round(est, 3), 'ci95': [round(lo, 3), round(hi, 3)], 'n_images': int(len(df)), 'n_cams': int(len(cams))}


def insight1_daily_rhythm(f):
    day = f[f['light'] == 'day']
    prof = f.groupby(['is_weekend', 'hour'])['vehicles'].mean().unstack(0).rename(columns=DAY).round(2)
    wk, we = prof['weekday'], prof['weekend']
    am = wk.loc[6:11].idxmax()
    pm = wk.loc[14:19].idxmax()
    daily = day.groupby(['date', 'hour'])['vehicles'].mean().unstack(0)
    wkdates = sorted(f.loc[f['is_weekend'] == 0, 'date'].unique())
    corr = daily[wkdates].corr().where(~np.eye(len(wkdates), dtype=bool)).stack()
    lvl = day.groupby('is_weekend')['vehicles'].mean()
    return {'hourly_profile': prof.reset_index().to_dict('records'),
            'weekday_am_peak': {'hour': int(am), 'veh': round(wk[am], 2)}, 'weekday_pm_peak': {'hour': int(pm), 'veh': round(wk[pm], 2)},
            'weekend_peak': {'hour': int(we.idxmax()), 'veh': round(we.max(), 2)},
            'weekend_vs_weekday_daylight_pct': round((lvl[1] / lvl[0] - 1) * 100, 1),
            'weekday_profile_corr_range': [round(corr.min(), 2), round(corr.max(), 2)],
            'weekday_profile_corr_matrix': daily[wkdates].corr().round(2).to_dict(),
            'daylight_hourly_by_date': daily.round(2).reset_index().to_dict('records'),
            'holidays_in_period': int(f['is_holiday'].max())}


def insight2_evening_vs_morning(f, prof):
    p = prof.dropna(subset=['am_peak', 'pm_peak']).copy()
    p['am_pm_ratio'] = p['am_peak'] / p['pm_peak']
    near = p['dist_rail_m'] <= 500
    rho, pv = stats.spearmanr(p['dist_rail_m'], p['am_pm_ratio'])
    peak_hour = (f[(f['is_weekend'] == 0) & (f['light'] == 'day')].groupby(['cam', 'hour'])['vehicles'].mean()
                 .groupby('cam').idxmax().map(lambda x: x[1]))
    return {'cams_evening_heavier': int((p['am_pm_ratio'] < 0.9).sum()), 'cams_morning_heavier': int((p['am_pm_ratio'] > 1.1).sum()),
            'cams_similar': int(p['am_pm_ratio'].between(0.9, 1.1).sum()),
            'median_ratio_near_rail_500m': round(p.loc[near, 'am_pm_ratio'].median(), 3), 'n_near_rail': int(near.sum()),
            'median_ratio_elsewhere': round(p.loc[~near, 'am_pm_ratio'].median(), 3),
            'mannwhitney_p_near_vs_else': round(stats.mannwhitneyu(p.loc[near, 'am_pm_ratio'], p.loc[~near, 'am_pm_ratio']).pvalue, 4) if near.sum() > 2 else None,
            'spearman_dist_rail_vs_ratio': {'rho': round(rho, 3), 'p': round(pv, 4)},
            'ratio_by_highway': p.groupby('highway')['am_pm_ratio'].median().round(3).to_dict(),
            'peak_hour_distribution': peak_hour.value_counts().sort_index().to_dict()}


def rain_block(f, day_flag, extra=None):
    sub = f[(f['is_weekend'] == day_flag) & (f['baseline_matched'] == 1) & (f['rain_level'] != 'unknown')]
    if extra is not None:
        sub = sub[extra(sub)]
    out = {}
    for lv in ['dry', 'light', 'heavy']:
        g = sub[sub['rain_level'] == lv]
        if len(g) >= 30:
            out[lv] = cluster_boot(g, 'cong_index')
    return out


def mixed_model(f):
    d = f[(f['baseline_matched'] == 1) & (f['rain_level'] != 'unknown')].copy()
    d['y'] = np.log(d['vehicles'] + 1)
    d['day'] = d['is_weekend'].map(DAY)
    m = smf.mixedlm("y ~ C(rain_level, Treatment('dry')) * C(day) + C(hour) + C(light)", d, groups=d['cam']).fit(method='lbfgs')
    keep = {k: v for k, v in m.params.items() if 'rain_level' in k}
    return {k: {'coef': round(v, 4), 'pct_change': round((np.exp(v) - 1) * 100, 1), 'p': round(m.pvalues[k], 4)} for k, v in keep.items()}


def insight3_weekday_rain(f):
    res = {'all_light': rain_block(f, 0), 'daylight_only': rain_block(f, 0, lambda s: s['light'] == 'day'),
           'dusk_night': rain_block(f, 0, lambda s: s['light'] != 'day'), 'mixed_model': mixed_model(f)}
    m = f.drop_duplicates(['date', 'hour'])[['date', 'hour', 'metar_rain', 'city_rain_share']]
    res['metar_agreement'] = {'hours_metar_rain': int((m['metar_rain'] > 0).sum()),
                              'of_which_city_share_gt_10pct': int(((m['metar_rain'] > 0) & (m['city_rain_share'] > 0.1)).sum()),
                              'hours_city_share_gt_10pct': int((m['city_rain_share'] > 0.1).sum())}
    om = f[(f['is_weekend'] == 0) & (f['baseline_matched'] == 1)]
    res['openmeteo_vs_station'] = {
        'images_rain_station': int((f['rain_level'].isin(['light', 'heavy'])).sum()),
        'images_rain_openmeteo': int((f['om_rain_level'].isin(['light', 'heavy'])).sum()),
        'agreement_pct': round(((f['rain_level'] == 'dry') == (f['om_rain_level'] == 'dry')).mean() * 100, 1),
        'weekday_effect_if_openmeteo_used': {lv: cluster_boot(om[om['om_rain_level'] == lv], 'cong_index') for lv in ['light', 'heavy']
                                             if (om['om_rain_level'] == lv).sum() >= 30}}
    res['rain_by_date_hour'] = (f[f['rain_level'].isin(['light', 'heavy'])].groupby(['date', 'hour']).size()
                                .reset_index(name='images').to_dict('records'))
    return res


def insight4_weekend_rain_flood(f, prof):
    res = {'weekend': rain_block(f, 1)}
    fl = f['flood_cm_max'].dropna()
    res['flood_sensors'] = {'images_with_sensor_within_1km': int(f['flood_cm_max'].notna().sum()),
                            'cams_with_sensor': int(f.loc[f['flood_cm_max'].notna(), 'cam'].nunique()),
                            'readings_above_0cm': int((fl > 0).sum()), 'max_cm': float(fl.max()) if len(fl) else None}
    rain = f[f['rain_level'].isin(['light', 'heavy']) & (f['baseline_matched'] == 1)]
    per = rain.groupby('cam')['cong_index'].apply(lambda x: np.exp(np.log(x).mean())).rename('rain_ratio').reset_index()
    per = per.merge(prof[['cam', 'flood_unfixed_500m', 'in_flood_hotspot', 'flood_kde']], on='cam')
    a, b = per[per['flood_unfixed_500m'] > 0]['rain_ratio'], per[per['flood_unfixed_500m'] == 0]['rain_ratio']
    res['unfixed_flood_points'] = {'cams_with_unfixed_500m': int(len(a)), 'median_rain_ratio_with': round(a.median(), 3),
                                   'median_rain_ratio_without': round(b.median(), 3),
                                   'mannwhitney_p': round(stats.mannwhitneyu(a, b).pvalue, 4) if len(a) > 2 and len(b) > 2 else None}
    h, nh = per[per['in_flood_hotspot'] == 1]['rain_ratio'], per[per['in_flood_hotspot'] == 0]['rain_ratio']
    res['dbscan_hotspot'] = {'cams_in_hotspot_with_rain': int(len(h)), 'median_with': round(h.median(), 3) if len(h) else None,
                             'median_without': round(nh.median(), 3),
                             'mannwhitney_p': round(stats.mannwhitneyu(h, nh).pvalue, 4) if len(h) > 2 else None}
    rho, p = stats.spearmanr(per['flood_kde'], per['rain_ratio'])
    res['kde_vs_rain_ratio'] = {'rho': round(rho, 3), 'p': round(p, 4)}
    return res


def insight5_weekend_places(f, prof):
    p = prof.dropna(subset=['veh_weekday', 'veh_weekend']).copy()
    p = p[p['veh_weekday'] >= 1]
    p['weekend_ratio'] = p['veh_weekend'] / p['veh_weekday']
    cols = [c for c in p.columns if c.startswith('poi_')]
    corr = {c: dict(zip(['rho', 'p'], [round(v, 3) for v in stats.spearmanr(p[c], p['weekend_ratio'])])) for c in cols}
    show = ['cam', 'name_th', 'name_en', 'district', 'veh_weekday', 'veh_weekend', 'weekend_ratio', 'poi_market', 'poi_mall', 'poi_office']
    return {'top_weekend': p.nlargest(5, 'weekend_ratio')[show].round(3).to_dict('records'),
            'bottom_weekend': p.nsmallest(5, 'weekend_ratio')[show].round(3).to_dict('records'),
            'median_ratio': round(p['weekend_ratio'].median(), 3),
            'poi_spearman': corr}


def insight6_places_and_fridays(f, prof):
    day = f[f['light'] == 'day']
    dist = day.groupby('district').agg(veh=('vehicles', 'mean'), cams=('cam', 'nunique')).query('cams >= 2').sort_values('veh', ascending=False)
    hw = prof.groupby('highway')['veh_mean'].agg(['median', 'count']).round(2)
    groups = [g['veh_mean'].values for _, g in prof.groupby('highway') if len(g) >= 3]
    eve = day[(day['hour'].between(16, 18)) & (day['is_weekend'] == 0)]
    return {'district_daylight': dist.round(2).reset_index().to_dict('records'),
            'highway_veh_median': hw.reset_index().to_dict('records'),
            'kruskal_highway_p': round(stats.kruskal(*groups).pvalue, 4) if len(groups) >= 2 else None,
            'weekday_evening_16_18_by_day': eve.groupby('weekday')['vehicles'].mean().round(2).to_dict()}


def insight7_vehicle_mix(f, prof):
    mix = f.groupby('highway')[['car', 'motorcycle', 'bus', 'truck', 'vehicles']].sum()
    share = (mix[['car', 'motorcycle', 'bus', 'truck']].div(mix['vehicles'], axis=0) * 100).round(1)
    rho, p = stats.spearmanr(prof['poi_food'], prof['moto_share'])
    day = f[f['light'] == 'day']
    th = day.groupby(['is_weekend', 'hour'])[['truck', 'vehicles']].sum()
    th = (th['truck'] / th['vehicles'] * 100).round(1).unstack(0).rename(columns=DAY)
    top = prof.nlargest(3, 'moto_share')[['cam', 'name_th', 'district', 'moto_share', 'poi_food', 'poi_office']].round(3)
    return {'share_by_highway_pct': share.reset_index().to_dict('records'), 'overall_share_pct': (f[['car', 'motorcycle', 'bus', 'truck']].sum() / f['vehicles'].sum() * 100).round(1).to_dict(),
            'moto_vs_food_spearman': {'rho': round(rho, 3), 'p': round(p, 4)}, 'top_moto_cams': top.to_dict('records'),
            'truck_share_by_hour_daylight': th.reset_index().to_dict('records')}


def main():
    f, prof = load()
    res = {'images_analysed': int(len(f)), 'vehicles_counted': int(f['vehicles'].sum()), 'cameras': int(f['cam'].nunique())}
    res['i1'] = insight1_daily_rhythm(f)
    res['i2'] = insight2_evening_vs_morning(f, prof)
    res['i3'] = insight3_weekday_rain(f)
    res['i4'] = insight4_weekend_rain_flood(f, prof)
    res['i5'] = insight5_weekend_places(f, prof)
    res['i6'] = insight6_places_and_fridays(f, prof)
    res['i7'] = insight7_vehicle_mix(f, prof)
    write_json(res, 'analysis.json')
    print('analysis written', {k: v for k, v in res.items() if not isinstance(v, dict)})


if __name__ == '__main__':
    main()

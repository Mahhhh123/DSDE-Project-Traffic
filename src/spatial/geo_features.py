import json

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import LineString
from sklearn.cluster import DBSCAN
from sklearn.neighbors import KernelDensity

from src.common.config import CFG, path, write_json

G = CFG['spatial']
METRIC = G['crs_metric']
RANK = ['motorway', 'trunk', 'primary', 'secondary', 'tertiary']
POI = ['mall', 'market', 'government', 'office', 'school', 'rail_station', 'bus_stop', 'food', 'hospital']


def points(df, lat='lat', lon='lon'):
    df = df.dropna(subset=[lat, lon])
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df[lon], df[lat]), crs='EPSG:4326').to_crs(METRIC)


def silver(name):
    return pd.read_parquet(path('silver', name + '.parquet'))


def main():
    cams = points(silver('cameras'))
    out = cams[['cam', 'lat', 'lon']].copy()
    summary = {'crs': METRIC, 'cameras': len(cams)}

    st = points(silver('rain_stations'))
    near = gpd.sjoin_nearest(cams[['cam', 'geometry']], st[['station', 'district', 'geometry']], distance_col='station_dist_m')
    near = near.drop_duplicates('cam')
    out = out.merge(near[['cam', 'station', 'district', 'station_dist_m']], on='cam', how='left')
    summary['station_dist_m_median'] = round(float(near['station_dist_m'].median()), 1)

    poi = points(silver('osm_poi'))
    buf = cams[['cam', 'geometry']].copy()
    buf['geometry'] = buf.buffer(G['poi_radius_m'])
    hits = gpd.sjoin(poi[['category', 'geometry']], buf, predicate='within')
    counts = hits.pivot_table(index='cam', columns='category', aggfunc='size', fill_value=0).reindex(columns=POI, fill_value=0)
    counts.columns = ['poi_' + c for c in counts.columns]
    out = out.merge(counts.reset_index(), on='cam', how='left').fillna({c: 0 for c in counts.columns})
    rail = poi[poi['category'] == 'rail_station']
    d = gpd.sjoin_nearest(cams[['cam', 'geometry']], rail[['geometry']], distance_col='dist_rail_m').drop_duplicates('cam')
    out = out.merge(d[['cam', 'dist_rail_m']], on='cam', how='left')

    roads = silver('osm_roads')
    roads = gpd.GeoDataFrame(roads, geometry=[LineString(json.loads(g)) for g in roads['geometry']], crs='EPSG:4326').to_crs(METRIC)
    rb = cams[['cam', 'geometry']].copy()
    rb['geometry'] = rb.buffer(G['road_radius_m'])
    rj = gpd.sjoin(roads[['highway', 'road_name', 'lanes', 'geometry']], rb, predicate='intersects')
    rj['rank'] = rj['highway'].map(RANK.index)
    best = rj.sort_values('rank').drop_duplicates('cam')[['cam', 'highway', 'road_name', 'lanes']]
    out = out.merge(best, on='cam', how='left')
    out['highway'] = out['highway'].fillna('minor')
    out['lanes_n'] = pd.to_numeric(out['lanes'], errors='coerce')
    summary['highway_counts'] = out['highway'].value_counts().to_dict()

    fr = points(silver('flood_risk_points'))
    fb = cams[['cam', 'geometry']].copy()
    fb['geometry'] = fb.buffer(G['flood_radius_m'])
    fj = gpd.sjoin(fr[['status', 'geometry']], fb, predicate='within')
    agg = fj.groupby('cam').agg(flood_points_500m=('status', 'size'), flood_unfixed_500m=('status', lambda s: int((s == 'unfixed').sum())))
    out = out.merge(agg.reset_index(), on='cam', how='left').fillna({'flood_points_500m': 0, 'flood_unfixed_500m': 0})

    f68 = points(silver('flood_risk_2568'))
    j68 = gpd.sjoin(f68[['geometry']], fb, predicate='within').groupby('cam').size().rename('flood_risk2568_500m')
    out = out.merge(j68.reset_index(), on='cam', how='left').fillna({'flood_risk2568_500m': 0})

    ev = silver('road_flood_events_2566')
    by_district = ev.groupby('district').size().rename('flood_events_2566_district')
    out['flood_events_2566_district'] = out['district'].map(by_district).fillna(0).astype(int)

    xy = np.c_[fr.geometry.x, fr.geometry.y]
    kde = KernelDensity(bandwidth=G['kde_bandwidth_m'], kernel='gaussian').fit(xy)
    dens = np.exp(kde.score_samples(np.c_[cams.geometry.x, cams.geometry.y])) * len(xy) * 1e6
    out['flood_kde'] = np.round(dens, 3)
    db = DBSCAN(eps=G['dbscan_eps_m'], min_samples=G['dbscan_min_samples']).fit(xy)
    fr['cluster'] = db.labels_
    hot = fr[fr['cluster'] >= 0]
    hull = hot.dissolve('cluster').convex_hull.buffer(100)
    inside = gpd.sjoin(cams[['cam', 'geometry']], gpd.GeoDataFrame(geometry=hull, crs=METRIC).reset_index(), predicate='within')
    out['in_flood_hotspot'] = out['cam'].isin(inside['cam']).astype(int)
    out['flood_hotspot_id'] = out['cam'].map(inside.drop_duplicates('cam').set_index('cam')['cluster']).fillna(-1).astype(int)
    summary['dbscan'] = {'points': len(fr), 'clusters': int(fr['cluster'].max() + 1), 'noise': int((fr['cluster'] == -1).sum()),
                         'cameras_in_hotspot': int(out['in_flood_hotspot'].sum())}

    sens = points(silver('flood_sensors'))
    sens = sens[sens['has_readings'] == 1]
    sb = cams[['cam', 'geometry']].copy()
    sb['geometry'] = sb.buffer(G['flood_sensor_radius_m'])
    sj = gpd.sjoin(sens[['sensor', 'geometry']], sb, predicate='within').groupby('cam')['sensor'].apply(lambda s: ','.join(sorted(s)))
    out['flood_sensors_1km'] = out['cam'].map(sj).fillna('')

    out.drop(columns=['lanes']).to_parquet(path('silver', 'camera_spatial.parquet'), index=False)
    fr.drop(columns='geometry').to_parquet(path('silver', 'flood_risk_clusters.parquet'), index=False)
    write_json(summary, 'spatial_summary.json')
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == '__main__':
    main()

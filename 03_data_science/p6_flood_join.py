import math
import os

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLEAN = os.path.join(ROOT, 'data', 'clean')
RADIUS = 500
SENSOR_RADIUS = 1000
STATUS = {'1': 'unfixed', '2': 'unfixed', '3': 'unfixed', '4': 'partial', '5': 'fixed'}


def haversine(lat, lon, lats, lons):
    la1, lo1, la2, lo2 = map(np.radians, (lat, lon, lats, lons))
    return 6371000 * 2 * np.arcsin(np.sqrt(np.sin((la2 - la1) / 2) ** 2 + np.cos(la1) * np.cos(la2) * np.sin((lo2 - lo1) / 2) ** 2))


def camera_flood_table():
    cams = pd.read_csv(os.path.join(ROOT, 'data', 'cameras.csv'))
    risk = pd.read_csv(os.path.join(CLEAN, 'flood_risk_points.csv'))
    risk['status_group'] = risk.status_num.astype(str).str[0].map(STATUS)
    risk68 = pd.read_csv(os.path.join(CLEAN, 'flood_risk_points_2568.csv'))
    sensors = pd.read_csv(os.path.join(CLEAN, 'bma_road_flood_sensors.csv'))
    reported = set(pd.read_csv(os.path.join(CLEAN, 'bma_road_flood_hourly.csv')).sensor)
    sensors = sensors[sensors.sensor.isin(reported)]
    rows = []
    for c in cams.itertuples():
        d = haversine(c.lat, c.lon, risk.y.values, risk.x.values)
        near = risk[d <= RADIUS]
        d68 = haversine(c.lat, c.lon, risk68.UTM_Y.values, risk68.UTM_X.values)
        ds = haversine(c.lat, c.lon, sensors.lat.values, sensors.lon.values)
        k = int(np.argmin(d))
        if (near.status_group == 'unfixed').any():
            group = 'near_unfixed'
        elif len(near):
            group = 'near_fixed_only'
        else:
            group = 'not_near'
        rows.append({'cam': c.cam, 'flood_group': group, 'risk_points_500m': len(near),
                     'unfixed_500m': int((near.status_group == 'unfixed').sum()), 'fixed_500m': int((near.status_group == 'fixed').sum()),
                     'partial_500m': int((near.status_group == 'partial').sum()), 'nearest_risk_m': round(float(d[k])),
                     'nearest_risk_name': risk.name.iloc[k], 'nearest_risk_status': risk.status_detail.iloc[k],
                     'near_2568_list': int(d68.min() <= RADIUS), 'nearest_sensor': sensors.sensor.iloc[int(np.argmin(ds))],
                     'nearest_sensor_m': round(float(ds.min()))})
    return pd.DataFrame(rows)


def main():
    table = camera_flood_table()
    table.to_csv(os.path.join(CLEAN, 'camera_flood_context.csv'), index=False)
    flood = pd.read_csv(os.path.join(CLEAN, 'bma_road_flood_hourly.csv'))
    flood['date'] = flood.query_time.str[:10]
    flood['hour'] = flood.query_time.str[11:13].astype(int)
    fact = pd.read_csv(os.path.join(CLEAN, 'fact_images.csv'))
    fact = fact.merge(table[['cam', 'flood_group', 'unfixed_500m', 'nearest_sensor', 'nearest_sensor_m']], on='cam', how='left')
    level = flood.rename(columns={'sensor': 'nearest_sensor'})[['nearest_sensor', 'date', 'hour', 'flood_cm']]
    fact = fact.merge(level, on=['nearest_sensor', 'date', 'hour'], how='left')
    fact.loc[fact.nearest_sensor_m > SENSOR_RADIUS, 'flood_cm'] = np.nan
    fact['road_flooded'] = (fact.flood_cm > 0).astype(int)
    fact.to_csv(os.path.join(CLEAN, 'fact_images_flood.csv'), index=False)
    print(table.flood_group.value_counts().to_dict())
    print('images with a flood sensor within %d m:' % SENSOR_RADIUS, int(fact.flood_cm.notna().sum()), '· with water on road:', int(fact.road_flooded.sum()))


if __name__ == '__main__':
    main()

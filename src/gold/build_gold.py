from pyspark.sql import functions as F

from src.common.config import CFG, path
from src.common.spark import spark, write

R = CFG['rain']


def view(name, df=None):
    df = df if df is not None else spark().read.parquet(path('silver', name + '.parquet'))
    df.createOrReplaceTempView(name)
    return df


def main():
    s = spark()
    for t in ['detections', 'calendar', 'rain_hourly', 'rain_stations', 'metar', 'openmeteo', 'flood_readings', 'cameras']:
        view(t)
    view('camera_spatial', s.read.parquet(path('silver', 'camera_spatial.parquet')))

    s.sql("""
        select r.query_at as slot, r.station, r.rf1h
        from rain_hourly r join rain_stations st on r.station = st.station
        where r.rf1h is not null
    """).cache().createOrReplaceTempView('rain_slot')
    s.sql(f"""
        select slot, avg(rf1h) as city_rain_mean, avg(case when rf1h >= {R['dry_below_mm']} then 1D else 0D end) as city_rain_share
        from rain_slot group by slot
    """).createOrReplaceTempView('rain_city')
    s.sql("""
        select date_trunc('hour', ts) as slot, max(rain_level) as metar_level
        from metar group by date_trunc('hour', ts)
    """).createOrReplaceTempView('metar_hour')
    s.sql("""
        select s.cam, date_trunc('hour', f.query_at) as slot, max(f.flood_cm) as flood_cm_max
        from flood_readings f
        join (select cam, explode(split(flood_sensors_1km, ',')) as sensor from camera_spatial where flood_sensors_1km != '') s
          on f.sensor = s.sensor
        where f.faulty = 0
        group by s.cam, date_trunc('hour', f.query_at)
    """).createOrReplaceTempView('flood_cam_hour')

    lvl = lambda c: (f"case when {c} is null then 'unknown' when {c} < {R['dry_below_mm']} then 'dry' "
                     f"when {c} < {R['heavy_from_mm']} then 'light' else 'heavy' end")
    fact = s.sql(f"""
        with base as (
          select d.*, date_trunc('hour', d.ts) as slot,
                 case when hour(d.ts) < 9 then 'เช้า' when hour(d.ts) < 12 then 'สาย' when hour(d.ts) < 16 then 'บ่าย'
                      when hour(d.ts) < 19 then 'เย็น' else 'ค่ำ' end as period
          from detections d
        )
        select b.image_id, b.cam, b.ts, b.date, b.hour, b.period,
               c.dow, c.weekday, c.is_weekend, c.is_holiday, c.day_type,
               case when b.ts < c.civil_dawn then 'night' when b.ts < c.sunrise then 'dawn'
                    when b.ts <= c.sunset then 'day' when b.ts <= c.civil_dusk then 'dusk' else 'night' end as light,
               b.vehicles, b.car, b.motorcycle, b.bus, b.truck, b.occupancy, b.brightness, b.mean_conf, b.count_outlier,
               cs.district, cs.highway, cs.station, cs.station_dist_m,
               coalesce(rn.rf1h, rc.city_rain_mean) as rain_mm,
               case when rn.rf1h is not null then 'station' when rc.city_rain_mean is not null then 'city_mean' else 'none' end as rain_source,
               coalesce(rp.rf1h, rcp.city_rain_mean) as rain_prev_mm,
               rc.city_rain_share, rcp.city_rain_share as city_rain_share_prev,
               coalesce(m.metar_level, 0) as metar_rain, coalesce(mp.metar_level, 0) as metar_rain_prev,
               om.precipitation as om_precip, omp.precipitation as om_precip_prev, omp.cloud_cover as om_cloud_prev,
               fl.flood_cm_max
        from base b
        join calendar c on b.date = c.date
        left join camera_spatial cs on b.cam = cs.cam
        left join rain_slot rn on rn.station = cs.station and rn.slot = b.slot + interval 1 hour
        left join rain_slot rp on rp.station = cs.station and rp.slot = b.slot
        left join rain_city rc on rc.slot = b.slot + interval 1 hour
        left join rain_city rcp on rcp.slot = b.slot
        left join metar_hour m on m.slot = b.slot
        left join metar_hour mp on mp.slot = b.slot - interval 1 hour
        left join openmeteo om on om.cam = b.cam and om.ts = b.slot + interval 1 hour
        left join openmeteo omp on omp.cam = b.cam and omp.ts = b.slot
        left join flood_cam_hour fl on fl.cam = b.cam and fl.slot = b.slot
    """)
    fact = (fact.withColumn('rain_level', F.expr(lvl('rain_mm')))
                .withColumn('rain_prev_level', F.expr(lvl('rain_prev_mm')))
                .withColumn('om_rain_level', F.expr(lvl('om_precip'))))
    view('fact0', fact)
    fact = s.sql("""
        with base as (
          select cam, hour, is_weekend, percentile_approx(vehicles, 0.5) as baseline, count(*) as baseline_n
          from fact0 where rain_level = 'dry' group by cam, hour, is_weekend
        )
        select f.*, b.baseline, b.baseline_n, case when b.baseline_n >= 3 then 1 else 0 end as baseline_matched,
               cast(f.vehicles + 1 as double) / (b.baseline + 1) as cong_index
        from fact0 f left join base b on f.cam = b.cam and f.hour = b.hour and f.is_weekend = b.is_weekend
    """)
    write(fact, 'gold', 'fact_images', partition_by='date')
    view('fact_images', s.read.parquet(path('gold', 'fact_images')))

    feat = s.sql("""
        select f.cam, cast(f.date as string) as date, f.hour, first(f.period) as period, first(f.dow) as dow, first(f.is_weekend) as is_weekend,
               first(f.is_holiday) as is_holiday, first(f.day_type) as day_type,
               element_at(array_sort(collect_list(f.light)), cast(ceil(count(*) / 2.0) as int)) as light,
               count(*) as n_images, avg(f.vehicles) as veh_mean, avg(f.car) as car_mean, avg(f.motorcycle) as moto_mean,
               avg(f.bus) as bus_mean, avg(f.truck) as truck_mean, avg(f.cong_index) as cong_mean,
               first(f.rain_mm) as rain_mm, first(f.rain_level) as rain_level, first(f.rain_prev_mm) as rain_prev_mm,
               first(f.rain_prev_level) as rain_prev_level, first(f.city_rain_share_prev) as city_rain_share_prev,
               first(f.metar_rain_prev) as metar_rain_prev, first(f.om_precip_prev) as om_precip_prev,
               first(f.om_cloud_prev) as om_cloud_prev, first(f.om_rain_level) as om_rain_level, max(f.flood_cm_max) as flood_cm_max
        from fact_images f
        where f.count_outlier = 0
        group by f.cam, f.date, f.hour
    """)
    static = s.read.parquet(path('silver', 'camera_spatial.parquet')).drop('station', 'flood_sensors_1km', 'road_name')
    feat = feat.join(static, 'cam', 'left').withColumn('cam', F.col('cam').cast('string'))
    write(feat, 'gold', 'features_cam_hr.parquet')

    prof = s.sql("""
        select cam, count(*) as images, avg(vehicles) as veh_mean,
               avg(case when is_weekend = 0 then vehicles end) as veh_weekday,
               avg(case when is_weekend = 1 then vehicles end) as veh_weekend,
               avg(case when is_weekend = 0 and hour between 7 and 8 then vehicles end) as am_peak,
               avg(case when is_weekend = 0 and hour between 16 and 17 then vehicles end) as pm_peak,
               sum(truck) / sum(vehicles) as truck_share, sum(motorcycle) / sum(vehicles) as moto_share,
               sum(bus) / sum(vehicles) as bus_share
        from fact_images group by cam
    """).join(s.read.parquet(path('silver', 'camera_spatial.parquet')), 'cam', 'left') \
        .join(s.read.parquet(path('silver', 'cameras.parquet')).select('cam', 'name_th', 'name_en'), 'cam', 'left')
    write(prof, 'gold', 'camera_profile.parquet')
    print('gold fact', s.read.parquet(path('gold', 'fact_images')).count(),
          'features', s.read.parquet(path('gold', 'features_cam_hr.parquet')).count())


if __name__ == '__main__':
    main()

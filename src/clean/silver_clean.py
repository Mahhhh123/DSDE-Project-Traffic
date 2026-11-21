from pyspark.sql import Window
from pyspark.sql import functions as F
from pyspark.sql import types as T

from src.common.config import CFG, path, write_json
from src.common.spark import spark, write

C = CFG['cleaning']
LAT0, LON0, LAT1, LON1 = C['bangkok_bbox']
START, END = str(CFG['period']['start']), str(CFG['period']['end'])
DQ = []


def bronze(name):
    return spark().read.parquet(path('bronze', name + '.parquet') if not name.endswith('/') else path('bronze', name[:-1]))


def rule(table, name, before, after_or_flagged, action):
    n_before = before if isinstance(before, int) else before.count()
    n = after_or_flagged if isinstance(after_or_flagged, int) else after_or_flagged.count()
    affected = n_before - n if action == 'drop' else n
    DQ.append({'table': table, 'rule': name, 'rows_before': n_before, 'rows_affected': affected, 'action': action})
    print('  [%s] %-55s %s %d / %d' % (table, name, action, affected, n_before))


def num(col):
    c = F.trim(F.col(col))
    return F.when(c.rlike(r'^-?\d+(\.\d+)?$'), c.cast('double'))


def be_ts(col):
    p = F.split(F.trim(F.col(col)), ' ')
    d = F.split(p.getItem(0), '/')
    iso = F.format_string('%04d-%s-%s %s:00', d.getItem(2).cast('int') - 543, d.getItem(1), d.getItem(0), p.getItem(1))
    return F.to_timestamp(iso)


def in_bbox(lat, lon):
    return F.col(lat).between(LAT0, LAT1) & F.col(lon).between(LON0, LON1)


def cameras():
    raw = bronze('cameras')
    n0 = raw.count()
    df = raw.select(F.col('camera_id').cast('int').alias('cam'), F.trim('location').alias('name_th'),
                    F.trim('location_detail').alias('detail_th'), F.trim('location_en').alias('name_en'),
                    F.col('latitude').cast('double').alias('lat'), F.col('longitude').cast('double').alias('lon'),
                    F.col('image_count').cast('int').alias('image_count_given'))
    df = df.withColumn('name_en', F.when(F.col('name_en').isin('connect BMAcctv', '0', ''), None).otherwise(F.col('name_en')))
    rule('cameras', 'english name placeholder ("connect BMAcctv"/"0") -> null', n0, df.filter(F.col('name_en').isNull()), 'set_null')
    bad = df.filter(~in_bbox('lat', 'lon') | F.col('lat').isNull())
    rule('cameras', 'coordinates missing or outside Bangkok bbox', n0, bad, 'flag')
    df = df.withColumn('coord_ok', F.when(in_bbox('lat', 'lon'), 1).otherwise(0))
    d = df.dropDuplicates(['cam'])
    rule('cameras', 'duplicate camera_id', n0, d, 'drop')
    write(d, 'silver', 'cameras.parquet')
    return d


def images(cams):
    idx = bronze('images_index')
    n0 = idx.count()
    jpg = idx.filter(F.lower('path').rlike(r'\.jpe?g$'))
    rule('images', 'non-image entries in zip', n0, jpg, 'drop')
    pat = r'(?:^|/)(\d+)/(\d+)_(.+?)_(\d{8})_(\d{6})\.jpe?g$'
    p = jpg.select('path', F.col('bytes').cast('long').alias('bytes'),
                   F.regexp_extract('path', pat, 1).alias('cam_s'), F.regexp_extract('path', pat, 3).alias('loc'),
                   F.regexp_extract('path', pat, 4).alias('d'), F.regexp_extract('path', pat, 5).alias('t'))
    ok = p.filter(F.col('cam_s') != '')
    rule('images', 'filename does not match <cam>/<cam>_<loc>_<yyyymmdd>_<hhmmss>.jpg', p, ok, 'drop')
    ok = (ok.withColumn('cam', F.col('cam_s').cast('int'))
          .withColumn('ts', F.to_timestamp(F.concat('d', 't'), 'yyyyMMddHHmmss'))
          .withColumn('location', F.split('loc', '_').getItem(0))
          .drop('cam_s', 'd', 't', 'loc'))
    win = ok.filter(F.to_date('ts').between(START, END) & F.hour('ts').between(CFG['period']['first_hour'], CFG['period']['last_hour']))
    rule('images', 'timestamp outside study window %s..%s 06-21h' % (START, END), ok, win, 'drop')
    dd = win.dropDuplicates(['cam', 'ts'])
    rule('images', 'duplicate (camera, timestamp)', win, dd, 'drop')
    known = dd.join(cams.select('cam'), 'cam', 'left_semi')
    rule('images', 'camera id not in cctv_info', dd, known, 'drop')

    stats = spark().read.parquet(path('bronze', 'image_stats'))
    df = known.join(stats.drop('bytes'), 'path', 'left')
    df = df.withColumn('is_broken', ((F.col('bytes') < C['broken_image_bytes']) | (F.coalesce('decode_ok', F.lit(0)) == 0)).cast('int'))
    rule('images', 'broken image (< %d bytes or cannot decode)' % C['broken_image_bytes'], df.count(), df.filter('is_broken = 1'), 'flag')

    w = Window.partitionBy('cam').orderBy('ts')
    h = F.col('dhash')
    df = (df.withColumn('prev_hash', F.lag(h).over(w)).withColumn('prev_bytes', F.lag('bytes').over(w))
          .withColumn('is_frozen', ((F.col('dhash') == F.col('prev_hash')) & (F.col('bytes') == F.col('prev_bytes')) & (F.col('is_broken') == 0)).cast('int'))
          .fillna(0, ['is_frozen'])
          .drop('prev_hash', 'prev_bytes'))
    rule('images', 'stale frame: identical to previous frame of same camera (same bytes + same dHash)',
         df.count(), df.filter('is_frozen = 1'), 'flag')
    df = (df.withColumn('date', F.to_date('ts')).withColumn('hour', F.hour('ts'))
          .withColumn('image_id', F.concat_ws('_', F.col('cam').cast('string'), F.date_format('ts', 'yyyyMMddHHmmss')))
          .withColumn('is_valid', ((F.col('is_broken') == 0) & (F.col('is_frozen') == 0)).cast('int')))
    rule('images', 'valid images kept for analysis', df.count(), df.filter('is_valid = 1'), 'keep')
    write(df, 'silver', 'images.parquet')

    comp = (df.groupBy('cam', 'date').agg(F.count('*').alias('images'), F.sum('is_valid').alias('valid'))
            .withColumn('expected', F.lit(91)).withColumn('completeness', F.round(F.col('valid') / 91, 3)))
    write(comp, 'silver', 'image_completeness.parquet')
    return df


def detections(imgs):
    boxes = spark().read.parquet(path('bronze', 'detections_raw'))
    n0 = boxes.count()
    b = boxes.filter(F.col('conf') >= C['yolo_conf'])
    rule('detections', 'box confidence < %.2f' % C['yolo_conf'], n0, b, 'drop')
    b = b.withColumn('area', (F.col('x2') - F.col('x1')) * (F.col('y2') - F.col('y1')))
    agg = b.groupBy('path').agg(
        *[F.sum(F.when(F.col('cls') == c, 1).otherwise(0)).alias(c) for c in ['car', 'motorcycle', 'bus', 'truck']],
        F.count('*').alias('vehicles'), F.sum('area').alias('box_area'), F.mean('conf').alias('mean_conf'))
    df = (imgs.filter('is_valid = 1').select('image_id', 'path', 'cam', 'ts', 'date', 'hour', 'width', 'height', 'brightness')
          .join(agg, 'path', 'left').fillna(0, ['car', 'motorcycle', 'bus', 'truck', 'vehicles', 'box_area'])
          .withColumn('occupancy', F.round(F.least(F.col('box_area') / (F.col('width') * F.col('height')), F.lit(1.0)), 4))
          .drop('box_area'))
    q = df.approxQuantile('vehicles', [0.999], 0.0001)[0]
    df = df.withColumn('count_outlier', (F.col('vehicles') > q).cast('int'))
    rule('detections', 'vehicle count above p99.9 (%.0f) flagged' % q, df.count(), df.filter('count_outlier = 1'), 'flag')
    write(df, 'silver', 'detections.parquet')
    return df


def rain():
    raw = bronze('bma_rain')
    n0 = raw.count()
    df = raw.select(F.trim('c00').alias('station'), F.trim('c01').alias('district'), F.trim('c02').alias('station_name'),
                    be_ts('c03').alias('reported_at'), F.col('c03').alias('reported_raw'),
                    num('c05').alias('rf15'), num('c07').alias('rf1h'), num('c08').alias('rf3h'), num('c11').alias('rf24h'),
                    F.to_timestamp(F.format_string('%s %s:00:00', F.col('query_date'), F.col('query_hour'))).alias('query_at'))
    rule('rain', 'Buddhist-era date (2569) converted to CE', n0, df.filter(F.col('reported_at').isNotNull()), 'convert')
    rule('rain', 'non-numeric rainfall ("-", blank) -> null', n0, df.filter(F.col('rf1h').isNull()), 'set_null')
    bad = (F.col('rf1h') < 0) | (F.col('rf1h') > C['rain_max_mm_per_hour'])
    rule('rain', 'rf1h negative or > %d mm/h -> null' % C['rain_max_mm_per_hour'], n0, df.filter(bad), 'set_null')
    df = df.withColumn('rf1h', F.when(bad, None).otherwise(F.col('rf1h')))
    stale = F.abs(F.unix_timestamp('reported_at') - F.unix_timestamp('query_at')) > 3600
    kept = df.filter(~stale)
    rule('rain', 'reading timestamp >1h away from requested hour (stale station)', n0, kept, 'drop')
    df = kept
    d = df.dropDuplicates(['station', 'query_at'])
    rule('rain', 'duplicate (station, hour)', df, d, 'drop')
    listed = d.select('station').distinct()
    slots = d.groupby('query_at').agg(F.min('rf1h').alias('slot_min_listed'), F.count('*').alias('listed'))
    grid = listed.crossJoin(slots)
    full = (grid.join(d, ['station', 'query_at'], 'left')
            .withColumn('rf1h_source', F.when(F.col('rf1h').isNotNull(), 'observed')
                        .when(F.col('slot_min_listed') == 0, 'imputed_zero').otherwise('censored'))
            .withColumn('rf1h', F.when(F.col('rf1h').isNotNull(), F.col('rf1h')).when(F.col('slot_min_listed') == 0, F.lit(0.0)))
            .withColumn('rf1h_upper', F.when(F.col('rf1h_source') == 'censored', F.col('slot_min_listed'))))
    n_full = full.count()
    rule('rain', 'page lists only top-51 stations by 1h rain: unlisted -> 0 when cutoff is 0', n_full, full.filter("rf1h_source = 'imputed_zero'"), 'impute')
    rule('rain', 'unlisted while cutoff > 0 -> censored (null, upper bound kept)', n_full, full.filter("rf1h_source = 'censored'"), 'set_null')
    d = full.drop('district', 'station_name')
    write(d, 'silver', 'rain_hourly.parquet')

    st = bronze('bma_rain_stations')
    st = st.select(F.col('rain_code').alias('station'), F.col('rain_shortname').alias('station_name'), F.col('district_name').alias('district'),
                   F.col('latitude').cast('double').alias('lat'), F.col('longitude').cast('double').alias('lon'))
    n1 = st.count()
    st2 = st.filter(in_bbox('lat', 'lon')).dropDuplicates(['station'])
    rule('rain_stations', 'station without valid coordinates or duplicate', n1, st2, 'drop')
    st3 = st2.join(d.filter(F.col('rf1h').isNotNull()).select('station').distinct(), 'station', 'left_semi')
    rule('rain_stations', 'station listed in metadata but never reported rainfall this week', st2, st3, 'drop')
    write(st3, 'silver', 'rain_stations.parquet')


def metar():
    raw = bronze('metar')
    n0 = raw.count()
    wx = F.when(F.col('wxcodes') == 'M', '').otherwise(F.col('wxcodes'))
    df = (raw.select('station', F.to_timestamp('valid').alias('ts'), num('tmpc').alias('temp_c'), num('relh').alias('rh'),
                     F.when(F.col('p01m') == 'T', 0.05).otherwise(num('p01m')).alias('precip_mm'), wx.alias('wx'))
          .withColumn('rain_level', F.when(F.col('wx').contains('TS') & F.col('wx').contains('RA'), 3)
                      .when(F.col('wx').contains('+RA'), 3)
                      .when(F.col('wx').rlike(r'(^|\s)(RA|SHRA)'), 2)
                      .when(F.col('wx').rlike('RA|DZ|SH|TS'), 1).otherwise(0)))
    rule('metar', 'missing weather code "M" -> empty, trace "T" -> 0.05 mm', n0, raw.filter("wxcodes = 'M' or p01m = 'T'"), 'convert')
    d = df.filter(F.col('ts').isNotNull()).dropDuplicates(['station', 'ts'])
    rule('metar', 'unparseable time or duplicate report', n0, d, 'drop')
    write(d, 'silver', 'metar.parquet')


def openmeteo():
    raw = bronze('openmeteo')
    n0 = raw.count()
    df = raw.select(F.col('cam').cast('int').alias('cam'), F.to_timestamp('time', "yyyy-MM-dd'T'HH:mm").alias('ts'),
                    *[F.col(c).cast('double').alias(c) for c in ['precipitation', 'rain', 'cloud_cover', 'temperature_2m', 'relative_humidity_2m']])
    d = df.dropna(subset=['ts', 'precipitation']).dropDuplicates(['cam', 'ts'])
    rule('openmeteo', 'missing value or duplicate (cam, hour)', n0, d, 'drop')
    write(d, 'silver', 'openmeteo.parquet')


def calendar():
    sun = bronze('sun')
    loc = lambda c: F.to_timestamp(c)
    s = sun.select(F.to_date('date').alias('date'), loc('civil_twilight_begin').alias('civil_dawn'), loc('sunrise').alias('sunrise'),
                   loc('sunset').alias('sunset'), loc('civil_twilight_end').alias('civil_dusk'))
    rule('sun', 'UTC timestamps converted to Asia/Bangkok', sun.count(), sun.count(), 'convert')
    hol = bronze('holidays')
    h = (hol.select(F.to_date(F.from_unixtime(F.col('data_date_ms').cast('long') / 1000)).alias('date'), 'name', 'type')
         .filter(F.col('type').rlike('Public|Bank|National')))
    rule('holidays', 'keep public/bank/national holidays only', hol.count(), h, 'drop')
    h = h.groupBy('date').agg(F.concat_ws(' / ', F.collect_set('name')).alias('holiday'))
    days = spark().sql("select explode(sequence(to_date('%s'), to_date('%s'), interval 1 day)) as date" % (START, END))
    cal = (days.join(s, 'date', 'left').join(h, 'date', 'left')
           .withColumn('dow', F.dayofweek('date'))
           .withColumn('weekday', F.date_format('date', 'E'))
           .withColumn('is_holiday', F.col('holiday').isNotNull().cast('int'))
           .withColumn('is_weekend', ((F.col('dow').isin(1, 7)) | (F.col('is_holiday') == 1)).cast('int'))
           .withColumn('day_type', F.when(F.col('is_weekend') == 1, 'weekend').otherwise('weekday')))
    write(cal, 'silver', 'calendar.parquet')


def osm():
    poi = bronze('osm_poi')
    n0 = poi.count()
    t = F.from_json('tags', T.MapType(T.StringType(), T.StringType()))
    p = poi.withColumn('t', t)
    g = lambda k: F.col('t').getItem(k)
    cat = (F.when(g('shop').isin('mall', 'department_store'), 'mall')
           .when(g('amenity') == 'marketplace', 'market')
           .when((g('office') == 'government') | (g('amenity') == 'townhall'), 'government')
           .when(g('office').isNotNull(), 'office')
           .when(g('amenity').isin('school', 'university', 'college'), 'school')
           .when(g('railway') == 'station', 'rail_station')
           .when(g('highway') == 'bus_stop', 'bus_stop')
           .when(g('amenity').isin('restaurant', 'cafe', 'fast_food'), 'food')
           .when(g('amenity').isin('hospital', 'clinic'), 'hospital'))
    p = p.select('osm_type', 'osm_id', F.col('lat').cast('double').alias('lat'), F.col('lon').cast('double').alias('lon'),
                 cat.alias('category'), g('name').alias('name'))
    k = p.filter(F.col('category').isNotNull() & F.col('lat').isNotNull()).dropDuplicates(['osm_type', 'osm_id'])
    rule('osm_poi', 'no matching category / no coordinates / duplicate', n0, k, 'drop')
    write(k, 'silver', 'osm_poi.parquet')
    r = bronze('osm_roads')
    rr = r.withColumn('t', t).select('osm_id', F.col('t').getItem('highway').alias('highway'), F.col('t').getItem('name').alias('road_name'),
                                     F.col('t').getItem('lanes').alias('lanes'), 'geometry')
    rr2 = rr.filter(F.size(F.from_json('geometry', T.ArrayType(T.ArrayType(T.DoubleType())))) >= 2).dropDuplicates(['osm_id'])
    rule('osm_roads', 'road with < 2 vertices or duplicate', r.count(), rr2, 'drop')
    write(rr2, 'silver', 'osm_roads.parquet')


def flood():
    raw = bronze('bma_flood')
    n0 = raw.count()
    df = raw.select(F.trim('c00').alias('sensor'), F.trim('c01').alias('road'), F.trim('c02').alias('name'),
                    be_ts('c03').alias('reported_at'), num('c04').alias('flood_cm'),
                    F.to_timestamp(F.format_string('%s %s:%s:00', 'query_date', F.substring('query_hhmm', 1, 2), F.substring('query_hhmm', 3, 2))).alias('query_at'))
    rule('flood_readings', 'non-numeric water level -> null', n0, df.filter(F.col('flood_cm').isNull()), 'set_null')
    d = df.dropDuplicates(['sensor', 'query_at'])
    rule('flood_readings', 'duplicate (sensor, slot)', df, d, 'drop')
    stats = d.groupBy('sensor').agg(F.count('flood_cm').alias('n_readings'), F.stddev('flood_cm').alias('sd'), F.max('flood_cm').alias('max_cm'))
    const = stats.filter((F.col('n_readings') > 10) & (F.coalesce('sd', F.lit(0.0)) == 0) & (F.col('max_cm') > 0))
    rule('flood_sensors', 'constant non-zero level all week (likely faulty sensor)', stats.count(), const, 'flag')
    d = d.join(const.select('sensor', F.lit(1).alias('faulty')), 'sensor', 'left').fillna(0, ['faulty'])
    write(d, 'silver', 'flood_readings.parquet')
    s = bronze('bma_flood_sensors')
    s = s.select(F.col('flood_code').alias('sensor'), F.col('flood_name').alias('name'), F.col('road_name').alias('road'),
                 F.col('latitude').cast('double').alias('lat'), F.col('longitude').cast('double').alias('lon'))
    n1 = s.count()
    s = s.filter(in_bbox('lat', 'lon')).dropDuplicates(['sensor'])
    rule('flood_sensors', 'sensor without valid coordinates', n1, s, 'drop')
    s = s.join(stats.select('sensor', (F.col('n_readings') > 0).cast('int').alias('has_readings')), 'sensor', 'left').fillna(0, ['has_readings'])
    rule('flood_sensors', 'sensor never reported a reading this week', s.count(), s.filter('has_readings = 0'), 'flag')
    write(s, 'silver', 'flood_sensors.parquet')


def open_data():
    fr = bronze('bma_flood_risk')
    n0 = fr.count()
    st = F.col('status_num').cast('int')
    df = fr.select(F.col('objectid').cast('int').alias('id'), F.trim('name').alias('name'), F.trim('district').alias('district'),
                   st.alias('status_num'), F.col('status_detail'),
                   F.when(st.isin(1, 2, 3), 'unfixed').when(st == 4, 'partial').when(st == 5, 'fixed').alias('status'),
                   F.col('y').cast('double').alias('lat'), F.col('x').cast('double').alias('lon'))
    rule('flood_risk_points', 'status 1/2/3 -> unfixed, 4 -> partial, 5 -> fixed', n0, df.filter(F.col('status').isNull()), 'map')
    k = df.filter(in_bbox('lat', 'lon'))
    rule('flood_risk_points', 'coordinates outside Bangkok', n0, k, 'drop')
    write(k, 'silver', 'flood_risk_points.parquet')

    f26 = bronze('bma_flood_risk26')
    k26 = f26.select(F.trim('DISTRICT_NAME').alias('district'), F.trim('STATION_NAME').alias('name'),
                     F.col('UTM_Y').cast('double').alias('lat'), F.col('UTM_X').cast('double').alias('lon')).filter(in_bbox('lat', 'lon'))
    rule('flood_risk_2568', 'columns named UTM_X/UTM_Y actually hold lon/lat degrees; outside bbox dropped', f26.count(), k26, 'drop')
    write(k26, 'silver', 'flood_risk_2568.parquet')

    ev = bronze('bma_frd_dds')
    e = ev.select(F.to_date('frd_rain_datestart', 'd/M/yyyy').alias('date'),
                  F.trim(F.regexp_replace('district', '^เขต', '')).alias('district'), F.trim('frd_road').alias('road'),
                  num('frd_flood_height').alias('flood_height_cm'), num('frd_total_rainfall').alias('rainfall_mm'))
    rule('road_flood_events_2566', 'cp874 file decoded; "เขต" prefix stripped from district', ev.count(), ev.count(), 'convert')
    write(e, 'silver', 'road_flood_events_2566.parquet')


def main():
    cams = cameras()
    imgs = images(cams)
    detections(imgs)
    rain()
    metar()
    openmeteo()
    calendar()
    osm()
    flood()
    open_data()
    write_json(DQ, 'dq_rules.json')


if __name__ == '__main__':
    main()

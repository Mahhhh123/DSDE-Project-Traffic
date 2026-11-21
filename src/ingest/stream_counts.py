import sys

from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql import types as T

from src.common import spark as _env
from src.common.config import CFG, path

K = CFG['kafka']
SCHEMA = T.StructType([T.StructField('image_id', T.StringType()), T.StructField('cam', T.IntegerType()), T.StructField('ts', T.StringType()),
                       T.StructField('vehicles', T.IntegerType()), T.StructField('car', T.IntegerType()), T.StructField('motorcycle', T.IntegerType()),
                       T.StructField('bus', T.IntegerType()), T.StructField('truck', T.IntegerType())])


def main(seconds=120):
    s = (SparkSession.builder.appName('cctv-stream').master('local[*]')
         .config('spark.jars.packages', 'org.apache.spark:spark-sql-kafka-0-10_2.13:4.0.1')
         .config('spark.sql.session.timeZone', 'Asia/Bangkok').config('spark.sql.shuffle.partitions', '3').getOrCreate())
    s.sparkContext.setLogLevel('ERROR')
    raw = (s.readStream.format('kafka').option('kafka.bootstrap.servers', K['bootstrap'])
           .option('subscribe', K['topic']).option('startingOffsets', 'earliest').load())
    ev = (raw.select(F.col('partition'), F.from_json(F.col('value').cast('string'), SCHEMA).alias('e'))
          .select('partition', 'e.*').withColumn('event_time', F.to_timestamp('ts')))
    agg = (ev.withWatermark('event_time', '20 minutes')
           .groupBy(F.window('event_time', '10 minutes'), 'cam')
           .agg(F.count('*').alias('frames'), F.avg('vehicles').alias('veh_mean'), F.sum('truck').alias('trucks'))
           .select(F.col('window.start').alias('window_start'), F.col('window.end').alias('window_end'), 'cam', 'frames', 'veh_mean', 'trucks'))
    q1 = (agg.writeStream.outputMode('append').format('parquet')
          .option('path', path('bronze', 'stream_counts_10min')).option('checkpointLocation', path('bronze', '_chk_stream_counts'))
          .trigger(processingTime='10 seconds').start())
    q2 = (ev.groupBy('partition').count().writeStream.outputMode('complete').format('console')
          .trigger(processingTime='10 seconds').start())
    q1.awaitTermination(seconds)
    q1.stop()
    q2.stop()
    out = s.read.parquet(path('bronze', 'stream_counts_10min'))
    print('stream windows written', out.count())
    out.orderBy('window_start', 'cam').show(10, truncate=False)


if __name__ == '__main__':
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 120)

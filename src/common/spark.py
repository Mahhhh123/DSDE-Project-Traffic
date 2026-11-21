import glob
import os

from src.common.config import CFG, path

for _jdk in ['/opt/homebrew/opt/openjdk@17', '/usr/local/opt/openjdk@17', *glob.glob('/Library/Java/JavaVirtualMachines/*17*/Contents/Home')]:
    if os.path.exists(os.path.join(_jdk, 'bin', 'java')):
        os.environ['JAVA_HOME'] = _jdk
        break

os.environ.setdefault('SPARK_LOCAL_IP', '127.0.0.1')
os.environ.setdefault('PYSPARK_PYTHON', __import__('sys').executable)

_spark = None


def spark():
    global _spark
    if _spark is None:
        from pyspark.sql import SparkSession
        _spark = (SparkSession.builder
                  .appName(CFG['project'])
                  .master('local[*]')
                  .config('spark.driver.memory', '6g')
                  .config('spark.sql.session.timeZone', 'Asia/Bangkok')
                  .config('spark.sql.shuffle.partitions', '8')
                  .config('spark.ui.showConsoleProgress', 'false')
                  .getOrCreate())
        _spark.sparkContext.setLogLevel('ERROR')
    return _spark


def read(layer, name):
    return spark().read.parquet(path(layer, name))


def write(df, layer, name, partition_by=None):
    from pyspark.sql import functions as F
    from pyspark.sql.types import TimestampType
    for f in df.schema.fields:
        if isinstance(f.dataType, TimestampType):
            df = df.withColumn(f.name, F.col(f.name).cast('timestamp_ntz'))
    w = df.write.mode('overwrite')
    if partition_by:
        w = w.partitionBy(partition_by)
    w.parquet(path(layer, name))
    return path(layer, name)

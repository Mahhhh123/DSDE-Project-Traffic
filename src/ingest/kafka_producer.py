import json
import sys
import time

import pandas as pd
from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError

from src.common.config import CFG, path

K = CFG['kafka']


def ensure_topic():
    admin = KafkaAdminClient(bootstrap_servers=K['bootstrap'])
    try:
        admin.create_topics([NewTopic(K['topic'], num_partitions=K['partitions'], replication_factor=1)])
    except TopicAlreadyExistsError:
        pass
    admin.close()


def main(date='2026-08-31', speedup=6000.0, limit=None):
    ensure_topic()
    df = pd.read_parquet(path('silver', 'detections.parquet'), columns=['image_id', 'cam', 'ts', 'vehicles', 'car', 'motorcycle', 'bus', 'truck'])
    df = df[df['ts'].dt.strftime('%Y-%m-%d') == date].sort_values('ts').head(limit)
    producer = KafkaProducer(bootstrap_servers=K['bootstrap'], key_serializer=lambda k: str(k).encode(),
                             value_serializer=lambda v: json.dumps(v, default=str).encode())
    prev = None
    for r in df.itertuples(index=False):
        if prev is not None:
            time.sleep(max((r.ts - prev).total_seconds() / speedup, 0))
        prev = r.ts
        producer.send(K['topic'], key=r.cam, value={'image_id': r.image_id, 'cam': int(r.cam), 'ts': r.ts.strftime('%Y-%m-%d %H:%M:%S'),
                                                    'vehicles': int(r.vehicles), 'car': int(r.car), 'motorcycle': int(r.motorcycle),
                                                    'bus': int(r.bus), 'truck': int(r.truck)})
    producer.flush()
    print('sent', len(df), 'events to', K['topic'])


if __name__ == '__main__':
    main(limit=int(sys.argv[sys.argv.index('--limit') + 1]) if '--limit' in sys.argv else None)

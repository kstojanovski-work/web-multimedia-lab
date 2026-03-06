from redis import Redis
from rq import Queue

from app.settings import REDIS_URL, RQ_QUEUE_NAME


def get_queue() -> Queue:
    redis = Redis.from_url(REDIS_URL)
    return Queue(RQ_QUEUE_NAME, connection=redis)

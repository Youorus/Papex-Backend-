import logging
import psycopg2
import redis
from django.conf import settings

logger = logging.getLogger(__name__)


def check_postgres():
    try:
        conn = psycopg2.connect(
            dbname=settings.DATABASES["default"]["NAME"],
            user=settings.DATABASES["default"]["USER"],
            password=settings.DATABASES["default"]["PASSWORD"],
            host=settings.DATABASES["default"]["HOST"],
            port=settings.DATABASES["default"]["PORT"],
            connect_timeout=3,
        )
        conn.close()
        logger.info("🟢 PostgreSQL OK")
        return True
    except Exception as e:
        logger.error(f"🔴 PostgreSQL FAILED: {e}")
        return False


def check_redis():
    try:
        client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        client.ping()
        logger.info("🟢 Redis OK")
        return True
    except Exception as e:
        logger.error(f"🔴 Redis FAILED: {e}")
        return False


def run_health_checks():
    pg = check_postgres()
    rd = check_redis()
    return pg and rd

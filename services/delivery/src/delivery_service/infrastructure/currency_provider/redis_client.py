from delivery_service.infrastructure.config import redis_settings
from redis.asyncio import Redis

redis_client: Redis = Redis.from_url(redis_settings.url)

"""Anti-Spam Service using Redis with in-memory fallback."""
import re
import time
from typing import Optional, Tuple, Dict, List
import redis.asyncio as aioredis
from app.config import settings
from utils.logging import get_logger

logger = get_logger(__name__)


class SpamService:
    def __init__(self) -> None:
        self.redis: Optional[aioredis.Redis] = None
        self._memory_cache: Dict[str, List[float]] = {}
        self._last_messages: Dict[str, List[str]] = {}

    async def init(self) -> None:
        """Initializes Redis connection if configured."""
        if settings.REDIS_URL:
            try:
                self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
                await self.redis.ping()
                logger.info("Connected to Redis for anti-spam rate limiting")
            except Exception as e:
                logger.warning(f"Could not connect to Redis ({e}), falling back to in-memory anti-spam rate limiter.")
                self.redis = None

    async def check_message_spam(
        self,
        chat_id: int,
        user_id: int,
        text: Optional[str]
    ) -> Tuple[bool, str]:
        """
        Evaluates whether a message is spam.
        Returns: (is_spam, reason)
        """
        if not text:
            return False, ""

        now = time.time()
        user_key = f"antispam:{chat_id}:{user_id}"

        # 1. Flood Detection (Rate limiting: max 5 messages in 5 seconds)
        if self.redis:
            try:
                pipe = self.redis.pipeline()
                pipe.zadd(user_key, {str(now): now})
                pipe.zremrangebyscore(user_key, 0, now - 5)
                pipe.zcard(user_key)
                pipe.expire(user_key, 10)
                results = await pipe.execute()
                count = results[2]
                if count > 5:
                    return True, f"Flood detected ({count} messages in 5s)"
            except Exception as e:
                logger.debug(f"Redis antispam check error: {e}")
        else:
            timestamps = self._memory_cache.setdefault(user_key, [])
            # Filter out timestamps older than 5 seconds
            timestamps = [ts for ts in timestamps if now - ts <= 5]
            timestamps.append(now)
            self._memory_cache[user_key] = timestamps
            if len(timestamps) > 5:
                return True, f"Flood detected ({len(timestamps)} messages in 5s)"

        # 2. Repeated Message Detection (identical message sent 3 times in a row)
        msg_key = f"msgs:{chat_id}:{user_id}"
        clean_text = text.strip().lower()
        recent = self._last_messages.setdefault(msg_key, [])
        recent.append(clean_text)
        if len(recent) > 3:
            recent.pop(0)
        if len(recent) >= 3 and len(set(recent)) == 1 and len(clean_text) > 3:
            return True, "Repeated identical messages"

        # 3. Excessive Links Detection (> 3 links in a single message)
        urls = re.findall(r"(?:https?://|t\.me/|www\.)\S+", text)
        if len(urls) > 3:
            return True, f"Excessive links ({len(urls)} links)"

        # 4. Excessive Mentions Detection (> 4 mentions in a single message)
        mentions = re.findall(r"@\w+", text)
        if len(mentions) > 4:
            return True, f"Excessive mentions ({len(mentions)} mentions)"

        return False, ""


spam_service = SpamService()

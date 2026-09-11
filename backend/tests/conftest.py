from unittest.mock import patch
import fakeredis

# Intercept redis.Redis calls to use fakeredis in tests
patcher = patch("redis.Redis", lambda **kwargs: fakeredis.FakeRedis(decode_responses=True))
patcher.start()

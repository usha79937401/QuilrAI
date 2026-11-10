import pytest
from task4_model_router.database import TokenDatabase
from task4_model_router.rate_limiter import SlidingWindowTokenLimiter, RateLimitExceeded

@pytest.mark.asyncio
async def test_sliding_window_quota(tmp_path):
    db = TokenDatabase(str(tmp_path / "usage.db"))
    limiter = SlidingWindowTokenLimiter(db, limit=100, window_seconds=60)
    await limiter.reserve("tenant-a", 60, now=1000)
    with pytest.raises(RateLimitExceeded):
        await limiter.reserve("tenant-a", 50, now=1001)
    result = await limiter.reserve("tenant-a", 50, now=1061)
    assert result["remaining"] == 50

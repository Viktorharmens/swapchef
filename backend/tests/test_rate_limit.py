import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rate_limit import RateLimiter


def test_limiet_per_adres():
    limiter = RateLimiter(per_minute=2)
    assert limiter.allow("a", now=0)
    assert limiter.allow("a", now=1)
    assert not limiter.allow("a", now=2)
    assert limiter.allow("b", now=2)


def test_venster_schuift_op():
    limiter = RateLimiter(per_minute=1)
    assert limiter.allow("a", now=0)
    assert not limiter.allow("a", now=59)
    assert limiter.allow("a", now=60)


def test_nul_zet_de_limiet_uit():
    limiter = RateLimiter(per_minute=0)
    assert all(limiter.allow("a", now=0) for _ in range(500))


def test_oude_adressen_worden_vergeten():
    limiter = RateLimiter(per_minute=5, max_keys=3)
    for i in range(10):
        limiter.allow(f"adres-{i}", now=i * 100)
    assert len(limiter._hits) <= 4

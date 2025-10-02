import time
from django.core.cache import cache

def set_rate(email: str, window=60, limit=3):
    key = f"pr_rl:{email}"
    hits = cache.get(key, 0)
    cache.set(key, hits + 1, window)
    return hits + 1 <= limit

def store_otp(email: str, otp: str, ttl=600):
    cache.set(f"pr_otp:{email}", {"otp": otp, "ts": int(time.time())}, ttl)

def get_otp(email: str):
    data = cache.get(f"pr_otp:{email}")
    return (data or {}).get("otp")

def delete_otp(email: str):
    cache.delete(f"pr_otp:{email}")

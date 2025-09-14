"""
Pre-generate JWT access tokens for a range of merchant users and push them
into a Redis list for Locust to consume (so Locust doesn't need to call /auth/token).

Run INSIDE the Django container to ensure settings are loaded, e.g.:
  docker compose exec wallet_web \
    python manage.py shell -c "exec(open('scripts/preload_tokens.py').read())"

Environment variables (picked from container env):
- REDIS_URL   (default: redis://redis:6379/0)
- TOKENS_KEY  (default: locust:tokens)
- TOKENS_START (default: 1)
- TOKENS_END   (default: 1000)
"""
import os
import redis
from django.contrib.auth.models import User
from rest_framework_simplejwt.tokens import AccessToken

REDIS_URL   = os.getenv("REDIS_URL", "redis://redis:6379/0")
TOKENS_KEY  = os.getenv("TOKENS_KEY", "locust:tokens")
START       = int(os.getenv("TOKENS_START", "1"))
END         = int(os.getenv("TOKENS_END", "1000"))

r = redis.from_url(REDIS_URL)
# Clear old list
r.delete(TOKENS_KEY)

count = 0
missing = 0
for i in range(START, END + 1):
    uname = f"m{i}"
    try:
        u = User.objects.get(username=uname)
    except User.DoesNotExist:
        missing += 1
        continue
    token = str(AccessToken.for_user(u))
    r.rpush(TOKENS_KEY, token)
    count += 1

print(f"[preload_tokens] pushed={count} missing_users={missing} range=[{START}..{END}] key='{TOKENS_KEY}' url='{REDIS_URL}'")

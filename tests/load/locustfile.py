from locust import FastHttpUser, task, between
import os, uuid, redis
from requests.exceptions import RequestException

REDIS_URL       = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
TOKENS_KEY      = os.getenv("TOKENS_KEY", "locust:tokens")
WITHDRAW_AMOUNT = os.getenv("WITHDRAW_AMOUNT", "1.00")
REQ_TIMEOUT     = float(os.getenv("REQ_TIMEOUT", "5"))

_r = redis.from_url(REDIS_URL)

class MerchantUser(FastHttpUser):
    host = os.getenv("TARGET_HOST", "http://127.0.0.1:8000")
    wait_time = between(0.01, 0.03)

    def on_start(self):
        t = _r.lpop(TOKENS_KEY)
        if t:
            self.token = t.decode() if isinstance(t, bytes) else t
        else:
            self.token = None

    @task
    def withdraw(self):
        if not self.token:
            return
        idem = str(uuid.uuid4())
        headers = {
            "Idempotency-Key": idem,
            "Authorization": f"Bearer {self.token}",
        }
        try:
            self.client.post(
                "/api/v1/withdrawals",
                json={"amount": WITHDRAW_AMOUNT},
                headers=headers,             
                name="/withdrawals",
                timeout=REQ_TIMEOUT,
            )
        except RequestException as e:
            self.environment.events.request.fire(
                request_type="POST", name="/withdrawals",
                response_time=0, response_length=0, exception=e, context={}
            )
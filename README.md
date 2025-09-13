<div dir="rtl" align="right">

<h1>سیستم واریز اعتباری پذیرنده (Django + FastAPI)</h1>

<p>
این مخزن یک پلتفرم پرداخت «صرفاً با پذیرنده» را پیاده‌سازی می‌کند. هر <b>پذیرنده</b> یک سقف اعتبار دارد که توسط <b>استخر اعتباری (CreditPool)</b> پشتیبانی می‌شود. بخش Django «هستهٔ سامانه» است و سرویس FastAPI «تسویه» را انجام می‌دهد.
</p>

<hr/>

<h2>فهرست مطالب</h2>
<ol>
  <li><a href="#overview">نمای کلی</a></li>
  <li><a href="#requirements">پیش‌نیازها و پورت‌ها</a></li>
  <li><a href="#bootstrap">راه‌اندازی سریع </a></li>
  <li><a href="#seed">Seed برای لود تست (۱۰۰۰ پذیرنده)</a></li>
  <li><a href="#security">امنیت سرویس تسویه (FastAPI)</a></li>
  <li><a href="#testing">تست‌های Unit و Integration</a></li>
  <li><a href="#load">لود تست با توکن‌های پیش‌تولید</a></li>
  <li><a href="#profiling">پروفایلینگ DB/Redis/PgBouncer</a></li>
  <li><a href="#requirements-mapping"> الزامات پیاده‌سازی</a></li>
  <li><a href="#troubleshoot">اشکال‌زدایی سریع</a></li>
</ol>

<hr/>

<h2 id="overview">۱) نمای کلی</h2>

<ul>
  <li>ادمین می‌تواند استخر اعتباری را شارژ کند.</li>
  <li>پذیرنده ثبت‌نام می‌کند؛ پس از تأیید ادمین، <code>WalletAccount</code> و <code>MerchantCredit</code> دریافت می‌کند.</li>
  <li>احراز هویت پذیرنده با JWT؛ با هر برداشت، هم اعتبار پذیرنده و هم <code>CreditPool</code> به‌صورت <b>اتمیک</b> کاهش می‌یابند.</li>
  <li>تسویه در سرویس <b>FastAPI</b>؛ فقط درخواست‌های دارای هدر داخلی معتبر را می‌پذیرد.</li>
  <li><b>Idempotency</b> و <b>لاگینگ</b> کامل برای همهٔ درخواست‌ها.</li>
  <li>Django + PostgreSQL، Celery + Redis؛ تست‌های Unit / Integration / Load.</li>
</ul>

<p><b>معماری ساده:</ب></p>
<pre dir="rtl"><code>Merchant → (JWT) → Django Core ──(X-Internal-Token)──▶ FastAPI Settlement
                │                           │
                ├── Idempotency/Logging     └── فقط درخواست از هسته پذیرفته می‌شود
                └── قفل ردیفی + تراکنش اتمیک روی MerchantCredit و CreditPool</code></pre>

<hr/>


<h2 id="bootstrap">۴) راه‌اندازی سریع </h2>

<ol>
  <li>بالا آوردن سرویس‌ها:
<pre dir="rtl"><code>docker compose up -d --build</code></pre>
  </li>

  <li>ایجاد ادمین Django:
<pre dir="rtl"><code>docker compose exec wallet_web python manage.py createsuperuser</code></pre>
  </li>

  <li><b>ورود ادمین و گرفتن توکن (ADMIN_ACCESS):</b>
<pre dir="rtl"><code> curl -s -X POST http://127.0.0.1:8000/api/v1/auth/token   -H "Content-Type: application/json"   -d '{"username":"admin","password":"&lt;ADMIN_PASSWORD&gt;"}'</code></pre>
  </li>

  <li>ثبت پذیرنده (API) — <i>نیاز به ادمین ندارد</i>:
<pre dir="rtl"><code>curl -s -X POST http://127.0.0.1:8000/api/v1/auth/register   -H "Content-Type: application/json"   -d '{"username":"m1","password":"p","requested_credit":"1000.00","bank_account":"IRTEST0000000000001"}'</code></pre>
  </li>

  <li>تأیید پذیرنده و تعیین سقف (ادمین) — <b>با توکن ادمین</b>:
<pre dir="rtl"><code>curl -s -X POST http://127.0.0.1:8000/api/v1/admin/approve   -H "Authorization: Bearer $ADMIN_ACCESS"   -H "Content-Type: application/json"   -d '{"merchant_id": 5004, "credit_limit": "1000.00"}'</code></pre>
  </li>

  <li>شارژ استخر اعتباری (ادمین) — <b>با توکن ادمین</b>:
<pre dir="rtl"><code>curl -s -X POST http://127.0.0.1:8000/api/v1/admin/pool/topup   -H "Authorization: Bearer $ADMIN_ACCESS"   -H "Content-Type: application/json"   -d '{"amount": "100000.00"}'</code></pre>
  </li>

  <div dir="rtl" align="right">

<h3>برداشت</h3>

<ol>
  <li><b>گرفتن توکن پذیرنده (خروجی را نگاه کن و مقدار access را کپی کن)</b>:
<pre><code>curl -s -X POST http://127.0.0.1:8000/api/v1/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"m1","password":"p"}'</code></pre>
  </li>
  

  <li><b>درخواست برداشت</b>:
<pre><code>curl -s -X POST http://127.0.0.1:8000/api/v1/withdrawals \
  -H "Authorization: Bearer $ACCESS" \
  -H "Idempotency-Key: $IDEM" \
  -H "Content-Type: application/json" \
  -d '{"amount":"1.00"}'</code></pre>
  </li>
</ol>

</div>


  <li>مشاهدهٔ پروفایل پذیرنده:
<pre dir="rtl"><code>curl -s http://127.0.0.1:8000/api/v1/me   -H "Authorization: Bearer $ACCESS"</code></pre>
  </li>
</ol>

<hr/>

<h2 id="seed">۵) Seed برای لود تست (۱۰۰۰ پذیرنده)</h2>

<p>اسکریپت زیر داده‌های قدیمی را پاک می‌کند و ۱۰۰۰ پذیرنده با پسورد <code>p</code> و سقف اعتبار <code>1000.00</code> می‌سازد و استخر را متناسب شارژ می‌کند:</p>

<pre dir="rtl"><code>docker compose exec -T wallet_web python manage.py shell &lt; scripts/seed_merchants.py
# خروجی نمونه:
# 🚀 Cleaning old data...
# ✅ Old data deleted
# 🎉 Seed done: merchants=1000, credit/merchant=1000.00, pool_available=5000000.00</code></pre>

<p>مشاهدهٔ وضعیت‌ها:</p>

<pre dir="rtl"><code># اعتبار یک پذیرنده (مثلاً m2)
docker compose exec db psql -U wallet -d walletdb -c" 
select u.username, mc.credit_limit, mc.utilized_amount
from payments_merchantcredit mc
join payments_merchant m on m.id = mc.merchant_id
join auth_user u on u.id = m.user_id
where u.username='m2';
"


# موجودی استخر
docker compose exec db psql -U wallet -d walletdb -c "select id, available_amount from payments_creditpool;"</code></pre>

<hr/>

<h2 id="security">۶) امنیت سرویس تسویه (FastAPI)</h2>

<ul>
  <li>فقط درخواست‌هایی که از هستهٔ Django می‌آیند پذیرفته می‌شوند: <code>X-Internal-Token: &lt;INTERNAL_TOKEN&gt;</code></li>
  <li>درخواست مستقیم بدون این هدر → <b>401/403</b>.</li>
  <li>آدرس داخلی: <code>http://settlement:9000/api/settlement/withdraw</code></li>
</ul>

<p>بدون هدر داخلی (رد می‌شود):</p>
<pre dir="rtl"><code>curl -i -s -X POST http://127.0.0.1:9000/api/settlement/withdraw   -H "Content-Type: application/json"   -d '{"merchant_id": 1, "account_id":"&lt;UUID&gt;", "amount":"1.00", "account":"IRTEST"}'</code></pre>

<p>با هدر داخلی (صرفاً تست مستقیم):</p>
<pre dir="rtl"><code>curl -i -s -X POST http://127.0.0.1:9000/api/settlement/withdraw   -H "Content-Type: application/json"   -H "X-Internal-Token: ChangeMeInternalToken123"   -d '{"merchant_id": 1, "account_id":"&lt;UUID&gt;", "amount":"1.00", "account":"IRTEST"}'</code></pre>

<hr/>

<h2 id="testing">۷) تست‌های Unit و Integration (Django)</h2>

<p><b>توصیه:</b> برای تست‌ها PgBouncer را دور بزنید تا ساخت/حذف DB تست ساده باشد.</p>

<p>اجرای همهٔ تست‌ها:</p>
<pre dir="rtl"><code>docker compose exec -e DB_HOST=db -e DB_PORT=5432 wallet_web   python manage.py test -v 2</code></pre>

<p>اگر Drop دیتابیس تست گیر کرد:</p>
<pre dir="rtl"><code>docker compose exec db psql -U wallet -d postgres -c "
SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='test_walletdb';
"
docker compose exec db psql -U wallet -d postgres -c "DROP DATABASE IF EXISTS test_walletdb;"</code></pre>

<p>اجرای یک تست خاص (کانکارنسی):</p>
<pre dir="rtl"><code>docker compose exec -e DB_HOST=db -e DB_PORT=5432 wallet_web   python manage.py test payments.tests.test_concurrent_withdrawals -v 2</code></pre>

<hr/>

<h2 id="load">۸) لود تست با توکن‌های پیش‌تولید</h2>

<p><b>گام ۱)</b> پیش‌تولید توکن‌ها و ذخیره در Redis</p>
<pre dir="rtl"><code>docker compose exec -T wallet_web python manage.py shell < scripts/preload_tokens.py</code></pre>

<p><b>گام ۲)</ب> اجرای Locust</p>
<pre dir="rtl"><code>N_TOKENS=1000 REDIS_URL=redis://127.0.0.1:6379/0 TARGET_HOST=http://127.0.0.1:8000 TOKENS_KEY=locust:tokens WITHDRAW_AMOUNT=1.00 locust -f tests/load/locustfile.py --headless   --users 500 --spawn-rate 50 --run-time 2m</code></pre>

<p>یا UI روی <code>http://localhost:8089</code>.</p>

<hr/>

<h2 id="profiling">۹) پروفایلینگ DB/Redis/PgBouncer</h2>

<pre dir="rtl"><code># PostgreSQL
docker compose exec db psql -U wallet -d walletdb -c "select * from pg_stat_activity;"
docker compose exec db psql -U wallet -d walletdb -c "select * from pg_locks;"

# PgBouncer
docker compose exec pgbouncer psql -p 6432 -U postgres -c 'show pools;'

# Redis
docker compose exec redis redis-cli INFO
docker compose exec redis redis-cli LLEN locust:tokens

# سیستم/کانتینر
docker stats</code></pre>

<hr/>

<h2 id="requirements-mapping">۱۰)  الزامات پیاده‌سازی (✅)</h2>

<ul>
  <li>✅ <b>منطق واریز پول در FastAPI</b>: Django پس از احراز هویت و بررسی اعتبار، سرویس FastAPI را صدا می‌زند.</li>
  <li>✅ <b>قبول فقط از هستهٔ Django</b>: FastAPI فقط با هدر <code>X-Internal-Token</code> معتبر درخواست را می‌پذیرد.</li>
  <li>✅ <b>عدم منفی شدن اعتبارها</b>: قبل از هر برداشت، هم اعتبار پذیرنده و هم <code>CreditPool.available_amount</code> بررسی می‌شود.</li>
  <li>✅ <b>لود موازی سنگین</b>: قفل ردیفی و تراکنش اتمیک؛ تست کانکارنسی + Locust.</li>
  <li>✅ <b>لاگینگ کامل</b>: <code>ApiRequestLog</code> و <code>LedgerEntry</code>.</li>
  <li>✅ <b>Idempotency</b>: با <code>Idempotency-Key</code>؛ درخواست تکراری پاسخ قبلی را برمی‌گرداند.</li>
  <li>✅ <b>مقاومت در برابر Race/Double-Spend</b>: تراکنش واحد + قفل روی <code>MerchantCredit</code> و <code>CreditPool</code>.</li>
</ul>

<hr/>

<h2 id="troubleshoot">۱۱) اشکال‌زدایی سریع</h2>

<ul>
  <li><b>401 از سرویس تسویه</b>: هدر <code>X-Internal-Token</code> را بررسی کنید.</li>
  <li><b>429 در لود تست</b>: Rate Limit را افزایش دهید یا غیرفعال کنید.</li>
  <li><b>503/Timeout</b>: ظرفیت Gunicorn/UVicorn/Workerها را بالا ببرید؛ <code>CONN_MAX_AGE</code> و <code>statement_timeout</code> را بهینه کنید.</li>
  <li><ب>مشکل تست با PgBouncer</ب>: برای تست‌ها از <code>DB_HOST=db</code> و <code>DB_PORT=5432</code> استفاده کنید.</li>
  <li><b>Drop نشدن DB تست</b>: <code>pg_terminate_backend</code> و سپس <code>DROP DATABASE</code>.</li>
</ul>

</div>

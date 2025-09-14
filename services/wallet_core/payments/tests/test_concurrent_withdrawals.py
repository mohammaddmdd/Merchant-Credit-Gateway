from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from decimal import Decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4
import threading

from django.db import transaction, connections, close_old_connections, connection

from payments.models import (
    Merchant, WalletAccount, MerchantCredit, CreditPool, atomic_consume_credit
)

class ConcurrentWithdrawalTests(TransactionTestCase):
    """
    20 تلاش همزمان برای برداشت 1.00 با سقف اعتبار 10.00
    انتظار: دقیقا 10 واحد مصرف، بدون دوخرجی/منفی شدن.
    """
    reset_sequences = True

    @classmethod
    def tearDownClass(cls):
        try:
            connections.close_all()
        finally:
            super().tearDownClass()

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username="race_user", password="p", is_active=True)
        self.merchant = Merchant.objects.create(
            user=self.user, is_approved=True,
            requested_credit=Decimal("10.00"),
            bank_account="IRRACE",
        )
        self.account = WalletAccount.objects.create(merchant=self.merchant)
        self.credit = MerchantCredit.objects.create(
            merchant=self.merchant,
            credit_limit=Decimal("10.00"),
            utilized_amount=Decimal("0.00"),
        )
        self.pool = CreditPool.get_solo()
        self.pool.available_amount = Decimal("1000.00")
        self.pool.save()

    def _worker(self, idem_key: str, amount: Decimal, barrier: threading.Barrier):
        close_old_connections()
        barrier.wait()  
        try:
            with transaction.atomic():
                atomic_consume_credit(self.merchant, self.account, amount)
            return ("ok", "")
        except Exception as e:
            return ("err", repr(e))
        finally:
            try: connection.close()
            except Exception: pass

    def test_concurrent_consumption(self):
        attempts = 20
        amount = Decimal("1.00")
        keys = [f"idem-{uuid4()}" for _ in range(attempts)]
        barrier = threading.Barrier(attempts)

        results = []
        with ThreadPoolExecutor(max_workers=attempts) as ex:
            futs = [ex.submit(self._worker, k, amount, barrier) for k in keys]
            for f in as_completed(futs):
                results.append(f.result())

        errs = [e for (s, e) in results if s == "err"]
        if errs:
            print("Worker errors sample:", errs[:3], " (total:", len(errs), ")")

        self.credit.refresh_from_db()
        self.pool.refresh_from_db()

        self.assertEqual(self.credit.utilized_amount, Decimal("10.00"))
        self.assertEqual(self.pool.available_amount, Decimal("990.00"))
        self.assertGreaterEqual(self.credit.credit_limit - self.credit.utilized_amount, Decimal("0.00"))

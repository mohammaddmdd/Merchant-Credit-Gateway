from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from payments.models import Merchant, WalletAccount, MerchantCredit, CreditPool, atomic_consume_credit

class UnitCreditTests(TestCase):
    def setUp(self):
        u = User.objects.create_user(username='m1', password='x')
        self.m = Merchant.objects.create(user=u, is_approved=True, requested_credit=Decimal('100.00'))
        self.acc = WalletAccount.objects.create(merchant=self.m)
        self.mc = MerchantCredit.objects.create(merchant=self.m, credit_limit=Decimal('500.00'), utilized_amount=Decimal('0.00'))
        self.pool = CreditPool.get_solo()
        self.pool.available_amount = Decimal('1000.00'); self.pool.save()

    def test_consume_ok(self):
        atomic_consume_credit(self.m, self.acc, Decimal('100.00'))
        self.m.refresh_from_db(); self.pool.refresh_from_db()
        self.assertEqual(self.m.credit.utilized_amount, Decimal('100.00'))
        self.assertEqual(self.pool.available_amount, Decimal('900.00'))

    def test_insufficient_merchant_credit(self):
        with self.assertRaises(ValueError):
            atomic_consume_credit(self.m, self.acc, Decimal('600.00'))

    def test_insufficient_pool(self):
        self.pool.available_amount = Decimal('50.00'); self.pool.save()
        with self.assertRaises(ValueError):
            atomic_consume_credit(self.m, self.acc, Decimal('100.00'))

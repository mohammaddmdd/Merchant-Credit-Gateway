from __future__ import annotations
from django.db import models, transaction
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from decimal import Decimal, ROUND_HALF_UP
import uuid
from django.db.models import Q, F
from decimal import Decimal

def q(x) -> Decimal:
    d = x if isinstance(x, Decimal) else Decimal(str(x))
    return d.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

class Merchant(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='merchant')
    is_approved = models.BooleanField(default=False)
    requested_credit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    bank_account = models.CharField(max_length=64, blank=True, default='')

class WalletAccount(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE, related_name='account')
    created_at = models.DateTimeField(auto_now_add=True)

class CreditPool(models.Model):
    id = models.IntegerField(primary_key=True, default=1, editable=False)
    available_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get_solo(cls) -> "CreditPool":
        obj, _ = cls.objects.get_or_create(id=1, defaults={'available_amount': Decimal('0.00')})
        return obj

    class Meta:
            constraints = [
                models.CheckConstraint(
                    check=Q(available_amount__gte=Decimal('0.00')),
                    name='pool_available_nonneg'
                ),
            ]        

class MerchantCredit(models.Model):
    merchant = models.OneToOneField(Merchant, on_delete=models.CASCADE, related_name='credit')
    credit_limit = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    utilized_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal('0.00'))
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
            constraints = [
                models.CheckConstraint(
                    check=Q(utilized_amount__gte=Decimal('0.00')),
                    name='mc_utilized_nonneg'
                ),
                models.CheckConstraint(
                    check=Q(credit_limit__gte=F('utilized_amount')),
                    name='mc_utilized_le_limit'
                ),
            ]

    @property
    def available(self) -> Decimal:
        return q(self.credit_limit) - q(self.utilized_amount)

class IdempotencyRecord(models.Model):
    key = models.CharField(max_length=80, unique=True)
    request_hash = models.CharField(max_length=64)
    response_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

class ApiRequestLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    path = models.CharField(max_length=200)
    method = models.CharField(max_length=10)
    status = models.IntegerField()
    actor = models.CharField(max_length=80, blank=True, default='')
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

class WithdrawalRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    account = models.ForeignKey(WalletAccount, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=18, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    status = models.CharField(max_length=12, default='PENDING')  # PENDING, SUCCESS, FAILED
    bank_reference = models.CharField(max_length=64, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

class LedgerEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tx_id = models.UUIDField(default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.CASCADE)
    account = models.ForeignKey(WalletAccount, on_delete=models.CASCADE)
    direction = models.CharField(max_length=6, choices=[('DEBIT','DEBIT'),('CREDIT','CREDIT')])
    source = models.CharField(max_length=24, choices=[('CREDIT_POOL','CREDIT_POOL'),('MERCHANT_CREDIT','MERCHANT_CREDIT')])
    amount = models.DecimalField(max_digits=18, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)


def atomic_consume_credit(merchant: Merchant, account: WalletAccount, amount: Decimal):
    amount = q(amount)
    pool = CreditPool.get_solo()
    with transaction.atomic():
        pool = CreditPool.objects.select_for_update().get(id=1)
        mc = MerchantCredit.objects.select_for_update().get(merchant=merchant)
        if mc.available < amount:
            raise ValueError('INSUFFICIENT_MERCHANT_CREDIT')
        if pool.available_amount < amount:
            raise ValueError('INSUFFICIENT_POOL')
        mc.utilized_amount = q(mc.utilized_amount) + amount
        pool.available_amount = q(pool.available_amount) - amount
        mc.save(update_fields=['utilized_amount','updated_at'])
        pool.save(update_fields=['available_amount','updated_at'])
        tx_id = uuid.uuid4()
        LedgerEntry.objects.create(
            tx_id=tx_id, merchant=merchant, account=account,
            direction='DEBIT', source='CREDIT_POOL', amount=amount
        )
        LedgerEntry.objects.create(
            tx_id=tx_id, merchant=merchant, account=account,
            direction='CREDIT', source='MERCHANT_CREDIT', amount=amount
        )
        return tx_id

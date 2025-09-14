from django.contrib.auth.models import User
from django.db import transaction
from .models import Merchant, WalletAccount, MerchantCredit


def create_merchant(username: str, password: str, requested_credit, bank_account='') -> Merchant:
    with transaction.atomic():
        user = User.objects.create_user(username=username, password=password, is_active=True)
        m = Merchant.objects.create(user=user, requested_credit=requested_credit, bank_account=bank_account, is_approved=False)
        WalletAccount.objects.create(merchant=m)
        MerchantCredit.objects.create(merchant=m, credit_limit=0, utilized_amount=0)
        return m


def approve_merchant(merchant_id: int, credit_limit) -> Merchant:
    with transaction.atomic():
        m = Merchant.objects.select_for_update().get(id=merchant_id)
        mc = m.credit
        m.is_approved = True
        mc.credit_limit = credit_limit
        m.save(update_fields=['is_approved'])
        mc.save(update_fields=['credit_limit','updated_at'])
        return m

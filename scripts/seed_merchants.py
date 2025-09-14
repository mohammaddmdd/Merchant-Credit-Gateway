from django.contrib.auth.models import User
from decimal import Decimal
from django.db import transaction
from payments.models import Merchant, WalletAccount, MerchantCredit, CreditPool

N = 1000
PASSWORD = "p"
CREDIT_LIMIT = Decimal("1000.00")
POOL_MULTIPLIER = 5  
print("🚀 Cleaning old data...")

with transaction.atomic():
    MerchantCredit.objects.all().delete()
    WalletAccount.objects.all().delete()
    Merchant.objects.all().delete()
    User.objects.exclude(is_superuser=True).delete()
    CreditPool.objects.all().delete()

    print("✅ Old data deleted")

    pool_total = CREDIT_LIMIT * N * POOL_MULTIPLIER
    pool = CreditPool.objects.create(id=1, available_amount=pool_total)

    wallet_fields = {f.name for f in WalletAccount._meta.get_fields() if hasattr(f, "name")}
    has_bank_account = "bank_account" in wallet_fields

    for i in range(1, N + 1):
        uname = f"m{i}"
        u = User.objects.create_user(username=uname, password=PASSWORD, is_active=True)

        m = Merchant.objects.create(user=u, is_approved=True)

        wa_kwargs = {"merchant": m}
        if has_bank_account:
            wa_kwargs["bank_account"] = f"IRTEST{str(i).zfill(19)}"  

        acc = WalletAccount.objects.create(**wa_kwargs)

        MerchantCredit.objects.create(merchant=m, credit_limit=CREDIT_LIMIT)

print(f"🎉 Seed done: merchants={N}, credit/merchant={CREDIT_LIMIT}, pool_available={pool.available_amount}")
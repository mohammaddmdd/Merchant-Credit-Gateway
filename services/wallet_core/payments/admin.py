from django.contrib import admin
from .models import Merchant, WalletAccount, CreditPool, MerchantCredit, WithdrawalRequest, LedgerEntry, ApiRequestLog, IdempotencyRecord

admin.site.register(Merchant)
admin.site.register(WalletAccount)
admin.site.register(CreditPool)
admin.site.register(MerchantCredit)
admin.site.register(WithdrawalRequest)
admin.site.register(LedgerEntry)
admin.site.register(ApiRequestLog)
admin.site.register(IdempotencyRecord)

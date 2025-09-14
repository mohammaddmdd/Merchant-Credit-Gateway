from rest_framework import serializers
from .models import Merchant, WalletAccount, MerchantCredit

class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    requested_credit = serializers.DecimalField(max_digits=18, decimal_places=2)
    bank_account = serializers.CharField(required=False, allow_blank=True)

class MerchantMeSerializer(serializers.Serializer):
    merchant_id = serializers.IntegerField()
    username = serializers.CharField()
    is_approved = serializers.BooleanField()
    account_id = serializers.UUIDField()
    bank_account = serializers.CharField(allow_blank=True)
    credit_limit = serializers.DecimalField(max_digits=18, decimal_places=2)
    utilized_amount = serializers.DecimalField(max_digits=18, decimal_places=2)
    available_credit = serializers.DecimalField(max_digits=18, decimal_places=2)

class ApproveSerializer(serializers.Serializer):
    merchant_id = serializers.IntegerField()
    credit_limit = serializers.DecimalField(max_digits=18, decimal_places=2)

class TopupPoolSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)

class WithdrawalCreateSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=18, decimal_places=2)

from __future__ import annotations
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
import requests, hashlib, json
from .utils.cache import cache_get, cache_set, cache_del, rate_limit_allow
from .tasks import dispatch_settlement
import os
from django.core.serializers.json import DjangoJSONEncoder
from .serializers import RegisterSerializer, ApproveSerializer, TopupPoolSerializer, WithdrawalCreateSerializer
from .models import Merchant, WalletAccount, MerchantCredit, CreditPool, WithdrawalRequest, IdempotencyRecord, ApiRequestLog
from .models import atomic_consume_credit
from .permissions import IsAdmin
from .services import create_merchant, approve_merchant

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['username'] = user.username
        return token

class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer

@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    s = RegisterSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    m = create_merchant(
        s.validated_data['username'], s.validated_data['password'], s.validated_data['requested_credit'], s.validated_data.get('bank_account',''))
    return Response({'merchant_id': m.id, 'status': 'PENDING_APPROVAL'}, status=201)

@api_view(['POST'])
@permission_classes([IsAdmin])
def admin_approve(request):
    s = ApproveSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    m = approve_merchant(s.validated_data['merchant_id'], s.validated_data['credit_limit'])
    return Response({'merchant_id': m.id, 'approved': True, 'credit_limit': str(m.credit.credit_limit)})

@api_view(['POST'])
@permission_classes([IsAdmin])
def admin_topup_pool(request):
    s = TopupPoolSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    pool = CreditPool.get_solo()
    with transaction.atomic():
        pool = CreditPool.objects.select_for_update().get(id=1)
        pool.available_amount = pool.available_amount + s.validated_data['amount']
        pool.save(update_fields=['available_amount','updated_at'])
    return Response({'pool_available': str(pool.available_amount)})

@api_view(['GET'])
def me(request):
    # Cached profile for 30 seconds to reduce DB load under heavy read traffic
    cache_key = f"me:{request.user.id}"
    cached = cache_get(cache_key)
    if cached:
        return Response(json.loads(cached))
    m = request.user.merchant
    mc = m.credit
    acc = m.account
    data = {
        'merchant_id': m.id,
        'username': request.user.username,
        'is_approved': m.is_approved,
        'account_id': acc.id,
        'bank_account': m.bank_account,
        'credit_limit': str(mc.credit_limit),
        'utilized_amount': str(mc.utilized_amount),
        'available_credit': str(mc.available),
    }
    cache_set(cache_key, json.dumps(data, cls=DjangoJSONEncoder), ttl_sec=30)    
    return Response(data)


def _log_request(request, status_code:int, payload:dict):
    ApiRequestLog.objects.create(
        path=request.path, method=request.method, status=status_code,
        actor=request.user.username if request.user.is_authenticated else '',
        payload=payload)

@api_view(['POST'])
def create_withdrawal(request):
    """
    Create a withdrawal request while enforcing per-merchant rate limits,
    supporting idempotency, and optionally offloading settlement to a Celery task.
    """
    # Rate limiting: configurable via env RL_WINDOW_SEC and RL_MAX_REQUESTS
    rl_window = int(os.getenv('RL_WINDOW_SEC', '60'))
    rl_limit = int(os.getenv('RL_MAX_REQUESTS', '120'))
    allow, remain = rate_limit_allow(f"merchant:{request.user.id}:withdrawals", rl_limit, rl_window)
    if not allow:
        _log_request(request, 429, {'phase':'ratelimit_exceeded'})
        return Response({'detail': 'RATE_LIMITED', 'retry_in_seconds': rl_window}, status=429)

    # Handle idempotency key; compute request hash
    idem_key = request.headers.get('Idempotency-Key')
    raw = json.dumps(request.data, sort_keys=True)
    req_hash = hashlib.sha256(raw.encode()).hexdigest()
    if idem_key:
        try:
            rec = IdempotencyRecord.objects.get(key=idem_key)
            if rec.request_hash == req_hash:
                return Response(rec.response_json, status=200)
            else:
                return Response({'detail':'IDEMPOTENCY_KEY_CONFLICT'}, status=409)
        except IdempotencyRecord.DoesNotExist:
            pass
    # Validate payload using serializer
    s = WithdrawalCreateSerializer(data=request.data)
    s.is_valid(raise_exception=True)
    m = request.user.merchant
    if not m.is_approved:
        return Response({'detail':'MERCHANT_NOT_APPROVED'}, status=403)
    account = m.account
    amt = s.validated_data['amount']

    # Create withdrawal record in PENDING state
    wr = WithdrawalRequest.objects.create(merchant=m, account=account, amount=amt, status='PENDING')

    # Async offloading if enabled via ASYNC_SETTLEMENT=1
    if os.getenv('ASYNC_SETTLEMENT','0') == '1':
        wr.status = 'QUEUED'
        wr.save(update_fields=['status'])
        dispatch_settlement.delay(str(wr.id))
        out = {'withdrawal_id': str(wr.id), 'status': 'QUEUED'}
        if idem_key:
            IdempotencyRecord.objects.create(key=idem_key, request_hash=req_hash, response_json=out)
        _log_request(request, 202, {'phase':'queued_async'})
        return Response(out, status=202)

    headers = {'Authorization': f"Bearer {settings.INTERNAL_TOKEN}", 'Content-Type': 'application/json'}
    try:
        r = requests.post(settings.SETTLEMENT_URL, json={
            'merchant_id': m.id,
            'account_id': str(account.id),
            'amount': str(amt),
            'bank_account': m.bank_account
        }, headers=headers, timeout=10)
        if r.status_code != 200:
            wr.status = 'FAILED'
            wr.save(update_fields=['status'])
            _log_request(request, r.status_code, {'phase':'settlement_failed','resp':r.text})
            return Response({'detail':'SETTLEMENT_FAILED'}, status=502)
        resp = r.json()
        if resp.get('status') != 'SUCCESS':
            wr.status = 'FAILED'
            wr.save(update_fields=['status'])
            return Response({'detail':'SETTLEMENT_REJECTED'}, status=502)
    except Exception as exc:
        wr.status = 'FAILED'
        wr.save(update_fields=['status'])
        _log_request(request, 502, {'phase':'settlement_exception','error':str(exc)})
        return Response({'detail':'SETTLEMENT_ERROR'}, status=502)

    try:
        tx_id = atomic_consume_credit(m, account, amt)
    except ValueError as ve:
        wr.status = 'FAILED'
        wr.save(update_fields=['status'])
        return Response({'detail': str(ve)}, status=409)

    wr.status = 'SUCCESS'
    wr.bank_reference = resp.get('bank_reference','')
    wr.save(update_fields=['status','bank_reference'])

    cache_del(f"me:{request.user.id}")

    out = {
        'withdrawal_id': str(wr.id),
        'status':'SUCCESS',
        'amount': str(amt),
        'bank_reference': wr.bank_reference,
        'tx_id': str(tx_id)
    }
    if idem_key:
        IdempotencyRecord.objects.create(key=idem_key, request_hash=req_hash, response_json=out)
    _log_request(request, 200, {'phase':'finalized','resp':out})
    return Response(out, status=200)

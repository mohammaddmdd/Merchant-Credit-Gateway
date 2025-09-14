from __future__ import annotations
import os
import requests
import json
from celery import shared_task
from django.conf import settings
from django.db import transaction
from .models import WithdrawalRequest
from .models import atomic_consume_credit

SESSION_TIMEOUT = float(os.getenv('SETTLEMENT_TIMEOUT', '2.5'))

@shared_task(bind=True, autoretry_for=(requests.RequestException,), retry_backoff=True, retry_jitter=True, retry_kwargs={'max_retries': 5})
def dispatch_settlement(self, withdrawal_id: str):
    """
    Celery task to perform settlement with the external FastAPI service.
    Adds exponential backoff and jitter for retries. Idempotent: checks WithdrawalRequest status.
    """
    wr = WithdrawalRequest.objects.select_for_update().get(id=withdrawal_id)
    if wr.status in ('SUCCESS', 'FAILED'):
        return {'status': wr.status, 'bank_reference': wr.bank_reference}

    m = wr.merchant
    acc = wr.account
    amt = wr.amount

    # Build request body and headers
    body = {
        'merchant_id': m.id,
        'account_id': str(acc.id),
        'amount': str(amt),
        'bank_account': m.bank_account,
    }
    headers = {
        'Authorization': f"Bearer {settings.INTERNAL_TOKEN}",
        'Content-Type': 'application/json',
    }

    # Call settlement service with retries on transient errors
    try:
        resp = requests.post(settings.SETTLEMENT_URL, json=body, headers=headers, timeout=SESSION_TIMEOUT)
        # For server errors, raise exception to trigger retry
        if resp.status_code >= 500:
            raise requests.RequestException(f"Upstream 5xx: {resp.status_code}")
        if resp.status_code != 200:
            # Client error: mark failed and return
            wr.status = 'FAILED'
            wr.save(update_fields=['status'])
            return {'status': 'FAILED', 'detail': 'Upstream error', 'code': resp.status_code}
        data = resp.json()
    except requests.RequestException:
        # When retries exhausted, mark as failed
        if self.request.retries >= self.max_retries:
            wr.status = 'FAILED'
            wr.save(update_fields=['status'])
        raise

    # Perform credit consumption and finalize transaction in a DB transaction
    with transaction.atomic():
        wr = WithdrawalRequest.objects.select_for_update().get(id=withdrawal_id)
        if wr.status == 'SUCCESS':
            return {'status': 'SUCCESS', 'bank_reference': wr.bank_reference}
        tx_id = atomic_consume_credit(m, acc, amt)
        wr.status = 'SUCCESS'
        wr.bank_reference = data.get('bank_reference', '')
        wr.save(update_fields=['status', 'bank_reference'])
    return {'status': 'SUCCESS', 'bank_reference': wr.bank_reference}
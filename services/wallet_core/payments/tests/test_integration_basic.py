from django.test import TestCase
from django.urls import reverse
from django.conf import settings
from django.contrib.auth.models import User
from rest_framework.test import APIClient
from decimal import Decimal
from payments.models import Merchant, WalletAccount, MerchantCredit, CreditPool

class IntegrationFlowTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user('admin', '', 'x'); self.admin.is_staff=True; self.admin.save()
        self.client.force_authenticate(self.admin)
        r = self.client.post('/api/v1/admin/pool/topup', {'amount': '1000.00'}, format='json')
        assert r.status_code == 200
        self.client.force_authenticate(None)

    def test_register_approve_withdraw(self):
        r = self.client.post('/api/v1/auth/register', {'username':'m1','password':'p','requested_credit':'500.00','bank_account':'IR123'}, format='json')
        self.assertEqual(r.status_code, 201)
        self.client.force_authenticate(self.admin)
        m_id = 1
        r = self.client.post('/api/v1/admin/approve', {'merchant_id': m_id, 'credit_limit':'500.00'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.client.force_authenticate(None)
        r = self.client.post('/api/v1/auth/token', {'username':'m1','password':'p'}, format='json')
        self.assertEqual(r.status_code, 200)
        token = r.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        r = self.client.get('/api/v1/me'); self.assertEqual(r.status_code, 200)
        old_url = settings.SETTLEMENT_URL
        settings.SETTLEMENT_URL = 'http://localhost:9/unreachable'
        r = self.client.post('/api/v1/withdrawals', {'amount':'100.00'}, format='json')
        self.assertNotEqual(r.status_code, 200)
        settings.SETTLEMENT_URL = old_url

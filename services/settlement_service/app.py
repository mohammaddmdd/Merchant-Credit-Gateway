from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, condecimal
from decimal import Decimal
import os

INTERNAL_TOKEN = os.getenv('INTERNAL_TOKEN', 'ChangeMeInternalToken123')

app = FastAPI(title='Settlement Service')

class WithdrawIn(BaseModel):
    merchant_id: int
    account_id: str
    amount: condecimal(max_digits=18, decimal_places=2)
    bank_account: str | None = None

@app.post('/api/settlement/withdraw')
def settlement_withdraw(payload: WithdrawIn, authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Missing bearer token')
    token = authorization.split(' ', 1)[1]
    if token != INTERNAL_TOKEN:
        raise HTTPException(status_code=403, detail='Forbidden')
    ref = f"BNK-{payload.merchant_id}-{payload.account_id[:8]}-{str(payload.amount).replace('.', '')}"
    return {'status': 'SUCCESS', 'bank_reference': ref}

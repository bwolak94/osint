from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import random
import hashlib
from datetime import datetime, timedelta

router = APIRouter(prefix="/api/v1/crypto-trace", tags=["crypto-trace"])

class CryptoTransaction(BaseModel):
    txid: str
    block_height: int
    timestamp: str
    from_address: str
    to_address: str
    amount: float
    currency: str
    usd_value: float
    is_mixer: bool
    is_exchange: bool
    risk_score: int
    labels: list[str]

class AddressInfo(BaseModel):
    address: str
    currency: str
    total_received: float
    total_sent: float
    balance: float
    tx_count: int
    first_seen: str
    last_seen: str
    risk_score: int
    risk_level: str
    labels: list[str]
    cluster_size: int

class CryptoTraceResult(BaseModel):
    address: str
    address_info: AddressInfo
    transactions: list[CryptoTransaction]
    connected_addresses: list[dict]
    risk_indicators: list[str]

@router.get("/trace", response_model=CryptoTraceResult)
async def trace_address(address: str, currency: str = "BTC", depth: int = 2):
    risk_score = random.randint(10, 95)
    risk_level = "critical" if risk_score > 80 else "high" if risk_score > 60 else "medium" if risk_score > 40 else "low"

    addr_info = AddressInfo(
        address=address,
        currency=currency,
        total_received=round(random.uniform(0.1, 50.0), 8),
        total_sent=round(random.uniform(0.01, 45.0), 8),
        balance=round(random.uniform(0, 5.0), 8),
        tx_count=random.randint(5, 200),
        first_seen=(datetime.utcnow() - timedelta(days=random.randint(30, 1000))).isoformat(),
        last_seen=(datetime.utcnow() - timedelta(days=random.randint(0, 30))).isoformat(),
        risk_score=risk_score,
        risk_level=risk_level,
        labels=random.sample(["darknet_market", "mixer", "exchange", "ransomware", "scam", "gambling", "defi"], random.randint(0, 3)),
        cluster_size=random.randint(1, 50)
    )

    txs = []
    for i in range(random.randint(5, 15)):
        amount = round(random.uniform(0.001, 5.0), 8)
        price = random.uniform(20000, 65000) if currency == "BTC" else random.uniform(1000, 4000)
        txs.append(CryptoTransaction(
            txid=hashlib.sha256(f"{address}{i}".encode()).hexdigest(),
            block_height=random.randint(700000, 840000),
            timestamp=(datetime.utcnow() - timedelta(days=random.randint(1, 200))).isoformat(),
            from_address=address if i % 2 == 0 else f"1{''.join([str(random.randint(0,9)) for _ in range(25)])}",
            to_address=f"3{''.join([str(random.randint(0,9)) for _ in range(25)])}" if i % 2 == 0 else address,
            amount=amount,
            currency=currency,
            usd_value=round(amount * price, 2),
            is_mixer=random.random() < 0.1,
            is_exchange=random.random() < 0.2,
            risk_score=random.randint(0, 100),
            labels=random.sample(["peer_to_peer", "exchange_deposit", "mixer_output", "darknet"], random.randint(0, 2))
        ))

    risk_indicators = []
    if any(t.is_mixer for t in txs):
        risk_indicators.append("Transactions through known mixing services")
    if risk_score > 60:
        risk_indicators.append("High cluster risk score from associated addresses")
    if "darknet_market" in addr_info.labels:
        risk_indicators.append("Address linked to darknet marketplace activity")

    return CryptoTraceResult(
        address=address,
        address_info=addr_info,
        transactions=txs,
        connected_addresses=[{"address": f"1addr{i}", "risk_score": random.randint(0, 100), "labels": []} for i in range(min(depth * 3, 8))],
        risk_indicators=risk_indicators
    )

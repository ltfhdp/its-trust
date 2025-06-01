# uvicorn trust_main:app --reload --port 8001

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

from logic import (
    get_computing_weight,
    calculate_initial_trust,
    get_direct_trust_score,
    calculate_updated_trust,
    should_blacklist
)

app = FastAPI()

# === Models ===
class TrustInitInput(BaseModel):
    ownership_type: str
    device_type: str
    memory_gb: float

class TrustUpdateInput(BaseModel):
    last_trust: float
    success: bool
    peer_ratings: Optional[List[float]] = None  # list of scores from 0.0 to 1.0
    centrality_raw: int = 0  # number of unique connections

class SecurityEvaluateInput(BaseModel):
    device_id: str
    conn_count_last_minute: int

# === Routes ===
@app.post("/trust/initial")
def trust_initial(data: TrustInitInput):
    score = calculate_initial_trust(data.ownership_type, data.memory_gb, data.device_type)
    return {"trust_score": score}

@app.get("/trust/weight/{device_type}")
def computing_weight(device_type: str):
    return {"computing_power": get_computing_weight(device_type)}

@app.post("/trust/calculate")
def calculate_trust(data: TrustUpdateInput):
    # 1. Direct trust (dari hasil interaksi)
    direct_trust = get_direct_trust_score(data.success)

    # 2. Indirect trust: rata-rata peer rating
    if data.peer_ratings:
        indirect = sum(data.peer_ratings) / len(data.peer_ratings)
    else:
        indirect = 0.5  # default jika tidak ada rating

    # 3. Centrality score dari jumlah koneksi unik
    unique = data.centrality_raw
    if unique <= 1:
        centrality = 0.2
    elif unique <= 20:
        centrality = 0.2 + 0.3 * ((unique - 1) / 19)
    elif unique <= 50:
        centrality = 0.5 + 0.2 * ((unique - 20) / 30)
    elif unique <= 100:
        centrality = 0.7 + 0.3 * ((unique - 50) / 50)
    else:
        centrality = 1.0

    # 4. Hitung trust baru
    updated = calculate_updated_trust(
        last_trust=data.last_trust,
        direct_trust=direct_trust,
        indirect_trust=indirect,
        centrality_score=centrality
    )

    return {
        "updated_trust": updated,
        "direct_trust": direct_trust,
        "indirect_trust": round(indirect, 4),
        "centrality_score": round(centrality, 4),
        "blacklisted": should_blacklist(updated)
    }

@app.post("/security/evaluate")
def security_evaluate(data: SecurityEvaluateInput):
    FLOOD_LIMIT = 15
    penalty = 0.0
    blacklist = False

    if data.conn_count_last_minute >= FLOOD_LIMIT:
        penalty = 0.1
        blacklist = True

    return {
        "penalty": penalty,
        "blacklisted": blacklist
    }

# uvicorn trust_main:app --reload --port 8001

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import numpy as np

from logic import (
    get_computing_weight,
    calculate_initial_trust,
    get_direct_trust_score,
    calculate_updated_trust,
    should_blacklist,
    evaluate_flooding_risk, 
    calculate_log_centrality
)

app = FastAPI()

# models
class PeerEvaluation(BaseModel):
    rating_score: float
    interaction_was_successful: bool

class TrustInitInput(BaseModel):
    ownership_type: str
    device_type: str
    memory_gb: float

class TrustUpdateInput(BaseModel):
    last_trust: float
    success: bool
    peer_evaluations: Optional[List[PeerEvaluation]] = None  
    centrality_raw: int = 0  # jumlah koneksi unik
    rater_id: Optional[str] = None
    rated_id: Optional[str] = None

class SecurityEvaluateInput(BaseModel):
    device_id: str
    conn_count_last_minute: int
    is_coordinator: bool = False

def calculate_validated_indirect_trust(peer_evaluations: List[PeerEvaluation]) -> float:
    if not peer_evaluations:
        return 0.0

    valid_ratings = []
    for evaluation in peer_evaluations:
        # rating >= 0.5 hanya valid jika interaksi sebelumnya sukses
        is_positive_rating_valid = (
            evaluation.rating_score >= 0.5 and
            evaluation.interaction_was_successful
        )

        # rating < 0.5 hanya valid jika interaksi sebelumnya gagal
        is_negative_rating_valid = (
            evaluation.rating_score < 0.5 and
            not evaluation.interaction_was_successful
        )

        if is_positive_rating_valid or is_negative_rating_valid:
            valid_ratings.append(evaluation.rating_score)

    if not valid_ratings:
        return 0.0

    return round(sum(valid_ratings) / len(valid_ratings), 4)

# routes
@app.get("/")
def root():
    return {"message": "Trust Service"}

@app.post("/trust/initial")
def trust_initial(data: TrustInitInput):
    trust_score = calculate_initial_trust(data.ownership_type, data.memory_gb, data.device_type)
    computing_power = get_computing_weight(data.device_type)
    
    return {
        "trust_score": trust_score,
        "computing_power": computing_power
    }

@app.get("/trust/weight/{device_type}")
def computing_weight(device_type: str):
    return {"computing_power": get_computing_weight(device_type)}

@app.post("/trust/calculate")
def calculate_trust(data: TrustUpdateInput):
    # 1. Direct Observation
    direct_trust = get_direct_trust_score(data.success)

    # 2. Indirect Observation
    if data.peer_evaluations:
        indirect_trust = calculate_validated_indirect_trust(data.peer_evaluations)
    else:
        indirect_trust = 0.0

    # 3. Centrality score dari jumlah koneksi unik
    centrality = calculate_log_centrality(data.centrality_raw)

    # 4. Hitung trust baru
    updated = calculate_updated_trust(
        last_trust=data.last_trust,
        direct_trust=direct_trust,
        indirect_trust=indirect_trust,
        centrality_score=centrality,
        centrality_raw=data.centrality_raw
    )

    return {
        "updated_trust": updated,
        "direct_trust": direct_trust,
        "indirect_trust": round(indirect_trust, 4),
        "centrality_score": round(centrality, 4),
        "blacklisted": should_blacklist(updated)
    }

@app.post("/security/evaluate")
def security_evaluate(data: SecurityEvaluateInput):
    flood_result = evaluate_flooding_risk(
        recent_connections=data.conn_count_last_minute,
        is_coordinator=data.is_coordinator,
    )
    
    return {
        "penalty": flood_result["penalty"],
        "threshold_used": flood_result["threshold"]
    }
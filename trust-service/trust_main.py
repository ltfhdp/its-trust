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
    rater_reputation: Optional[str] = "AVERAGE"

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
    rated_reputation: Optional[str] = "AVERAGE"
    interaction_count: int = 1

class SecurityEvaluateInput(BaseModel):
    source_id: str
    conn_count_last_period: int
    is_coordinator: bool = False

def calculate_validated_indirect_trust(peer_evaluations: List[PeerEvaluation], rated_reputation: str) -> tuple[float, str]:
    if not peer_evaluations:
        return None, "cool_start"

    valid_ratings = []
    invalid_count = 0

    for evaluation in peer_evaluations:
        score = evaluation.rating_score
        success = evaluation.interaction_was_successful
        rater_rep = evaluation.rater_reputation 

        if rater_rep in ["BLACKLISTED", "VERY_SUSPICIOUS"]:
            invalid_count += 1
            continue
        is_valid = True
        if score >= 0.5 and success:
            valid_ratings.append(score)
        elif score < 0.5:
            if not success:
                valid_ratings.append(score)
            elif rated_reputation in ["POOR", "SUSPICIOUS", "BLACKLISTED"]:
                valid_ratings.append(score)
            else:
                is_valid = False
                invalid_count += 1
        else: 
            is_valid = False
            invalid_count +=1

    if not valid_ratings:
        return 0.0, "ignored"

    return round(sum(valid_ratings) / len(valid_ratings), 3), "validated"

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
    indirect_trust_val, indirect_status = calculate_validated_indirect_trust(data.peer_evaluations, data.rated_reputation)

    indirect_trust = None
    if data.interaction_count <= 1:
        # interaksi pertama, indirect none untuk mengurangi cold start
        indirect_trust = None
    elif indirect_status in ["ignored", "cool_start"]:
        #interaksi selanjutnya tanpa rating valid
        indirect_trust = 0.0
    else:
        #rating valid
        indirect_trust = indirect_trust_val

    # 3. Centrality score dari jumlah koneksi unik
    centrality = calculate_log_centrality(data.centrality_raw)

    # 4. Hitung trust baru
    updated = calculate_updated_trust(
        last_trust=data.last_trust,
        direct_trust=direct_trust,
        indirect_trust=indirect_trust,
        centrality_score=centrality
    )

    return {
        "updated_trust": updated,
        "direct_trust": direct_trust,
        "indirect_trust": round(indirect_trust, 3) if indirect_trust is not None else None,
        "indirect_status": indirect_status,
        "centrality_score": round(centrality, 3),
        "blacklisted": should_blacklist(updated)
    }

@app.post("/security/evaluate")
def security_evaluate(data: SecurityEvaluateInput):
    flood_result = evaluate_flooding_risk(
        recent_connections=data.conn_count_last_period,
        is_coordinator=data.is_coordinator,
    )
    
    return {
        "penalty": flood_result["penalty"],
        "threshold_used": flood_result["threshold"]
    }
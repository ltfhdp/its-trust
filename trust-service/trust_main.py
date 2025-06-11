# uvicorn trust_main:app --reload --port 8001

from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

from logic import (
    get_computing_weight,
    calculate_initial_trust,
    get_direct_trust_score,
    calculate_updated_trust,
    should_blacklist,
    evaluate_flooding_risk
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
    rater_id: Optional[str] = None
    rated_id: Optional[str] = None

class SecurityEvaluateInput(BaseModel):
    device_id: str
    conn_count_last_minute: int
    is_coordinator: bool = False
    total_active_devices: int = 0

def calculate_consensus_indirect_trust(peer_ratings: List[float]) -> float:
    """
    Hitung indirect trust dengan outlier detection - outlier langsung bikin trust turun
    """
    if not peer_ratings or len(peer_ratings) == 0:
        return 0.0
    
    if len(peer_ratings) == 1:
        return peer_ratings[0]  # Single rating, langsung pakai
    
    # Hitung statistics
    avg_rating = sum(peer_ratings) / len(peer_ratings)
    std_dev = (sum((x - avg_rating) ** 2 for x in peer_ratings) / len(peer_ratings)) ** 0.5
    
    # Deteksi outliers (nilai yang jauh dari rata-rata)
    outlier_threshold = max(0.25, 1.5 * std_dev)  # Minimal 0.25 atau 1.5 std dev
    outliers = [r for r in peer_ratings if abs(r - avg_rating) > outlier_threshold]
    
    # Filter outliers
    filtered_ratings = [r for r in peer_ratings if abs(r - avg_rating) <= outlier_threshold]
    
    if len(filtered_ratings) == 0:
        # Semua rating outlier - trust turun drastis karena inconsistent
        return max(0.1, avg_rating * 0.5)  # Penalty untuk inconsistency
    
    # Pakai rata-rata yang sudah di-filter
    filtered_avg = sum(filtered_ratings) / len(filtered_ratings)
    
    # Apply penalty berdasarkan jumlah outlier
    outlier_penalty = min(0.2, len(outliers) * 0.05)  # Max penalty 0.2
    
    final_indirect = max(0.0, filtered_avg - outlier_penalty)
    
    return round(final_indirect, 4)

# === Routes ===
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
    # 1. Direct trust (dari hasil interaksi)
    direct_trust = get_direct_trust_score(data.success)

    # 2. Enhanced Indirect trust dengan outlier detection
    if data.peer_ratings:
        indirect_trust = calculate_consensus_indirect_trust(data.peer_ratings)
    else:
        indirect_trust = 0.0

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
        indirect_trust=indirect_trust,
        centrality_score=centrality
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
        device_count=data.total_active_devices
    )
    
    return {
        "penalty": flood_result["penalty"],
        "blacklisted": flood_result["is_flooding"] and flood_result["risk_level"] == "severe",
        "risk_level": flood_result["risk_level"],
        "threshold_used": flood_result["threshold"],
        "connections_detected": data.conn_count_last_minute
    }
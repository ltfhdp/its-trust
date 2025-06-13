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

def calculate_consensus_indirect_trust(peer_ratings: list[float]) -> float:
    """
    Menghitung indirect trust menggunakan metode clustering sederhana.
    Metode ini mengasumsikan kelompok rating terbesar adalah konsensus yang benar.
    """
    if not peer_ratings:
        return 0.0
    
    n = len(peer_ratings)
    if n == 1:
        return peer_ratings[0]

    # 1. Urutkan rating untuk menemukan pola
    ratings = sorted(peer_ratings)

    # 2. Cari "celah" terbesar antara rating yang berurutan untuk menemukan pemisah
    if n > 2:
        # Hitung semua jarak/celah antara rating yang berdekatan
        gaps = [ratings[i+1] - ratings[i] for i in range(n - 1)]
        # Cari indeks dari celah yang paling besar
        max_gap_index = np.argmax(gaps)
        max_gap_value = gaps[max_gap_index]
    else: # Kasus khusus jika hanya ada 2 rating
        max_gap_index = 0
        max_gap_value = ratings[1] - ratings[0]

    # 3. Jika celah cukup besar (di atas 0.3), pisahkan data menjadi dua kelompok
    if max_gap_value > 0.3:
        # Kelompok 1: dari awal sampai ke lokasi celah terbesar
        cluster1 = ratings[:max_gap_index + 1]
        # Kelompok 2: sisa datanya
        cluster2 = ratings[max_gap_index + 1:]
        
        # 4. Tentukan kelompok mana yang merupakan konsensus (mayoritas)
        if len(cluster1) > len(cluster2):
            consensus_cluster = cluster1
            outlier_cluster = cluster2
        elif len(cluster2) > len(cluster1):
            consensus_cluster = cluster2
            outlier_cluster = cluster1
        else:
            # Jika jumlah anggota sama, pilih kelompok dengan nilai rata-rata lebih tinggi
            consensus_cluster = cluster2 if sum(cluster2) > sum(cluster1) else cluster1
            outlier_cluster = cluster1 if consensus_cluster is cluster2 else cluster2

        # 5. Hitung skor akhir dari kelompok konsensus + penalti dari jumlah outlier
        filtered_avg = sum(consensus_cluster) / len(consensus_cluster)
        outlier_penalty = min(0.1, len(outlier_cluster) * 0.005) # Maksimal penalti 0.2
        
        return round(max(0.0, filtered_avg - outlier_penalty), 4)
    else:
        # Jika tidak ada celah yang signifikan (semua rating kompak), pakai rata-rata biasa
        return round(sum(ratings) / n, 4)

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
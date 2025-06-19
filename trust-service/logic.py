from enum import Enum
import math

def normalize(value: float, max_value: float = 16.0) -> float:
    return min(value / max_value, 1.0)

class DeviceType(Enum):
    RSU = "RSU"
    COMPUTER = "Computer"
    SMARTPHONE = "Smartphone"
    SMART_DEVICE = "Smart Device"
    SENSOR = "Sensor"
    RFID = "RFID"

def get_computing_weight(device_type: str) -> float:
    weights = {
        "RSU": 1.0,
        "Computer": 0.9,
        "Smartphone": 0.8,
        "Smart Device": 0.6,
        "Sensor": 0.4,
        "RFID": 0.2
    }
    return weights.get(device_type, 0.5)

def get_memory_weight(memory_gb: float) -> float:
    if memory_gb <= 2:
        return 0.2
    elif memory_gb <= 4:
        return 0.4
    elif memory_gb <= 8:
        return 0.6
    elif memory_gb <= 16:
        return 0.8
    else:
        return 1.0

def calculate_initial_trust(ownership_type: str, memory_gb: float, device_type: str) -> float:
    if ownership_type.lower() == "internal":
        mem_weight = get_memory_weight(memory_gb)
        comp_weight = get_computing_weight(device_type)  # default RSU for internal
        relationship_factor = 1
        return round(0.5*relationship_factor + 0.5*((mem_weight + comp_weight) / 2), 3)
    else:
        return 0.5

def get_direct_trust_score(success: bool) -> float:
    return 0.01 if success else -0.01

def calculate_log_centrality(unique_connections: int) -> float:
    """
    Menghitung skor sentralitas menggunakan skala logaritmik.
    Ini memberikan kenaikan yang cepat di awal dan melambat di akhir.
    """
    # --- Parameter yang bisa Anda tuning ---
    # Jumlah koneksi di mana skor dianggap maksimal.
    MAX_CONNECTIONS = 100.0
    # Skor minimal untuk 1 koneksi (untuk mengatasi cold start).
    MIN_SCORE = 0.30
    # Skor maksimal yang bisa dicapai.
    MAX_SCORE = 1.0
    # ------------------------------------

    if unique_connections <= 0:
        return 0.0
    if unique_connections == 1:
        return MIN_SCORE
    if unique_connections >= MAX_CONNECTIONS:
        return MAX_SCORE

    # Logaritma dari nilai saat ini dan nilai maksimal.
    # Menggunakan log(koneksi) agar skalanya logaritmik.
    log_unique = math.log(unique_connections)
    log_max = math.log(MAX_CONNECTIONS)

    # Lakukan interpolasi pada skala logaritmik.
    scale = log_unique / log_max
    
    # Hitung skor akhir berdasarkan skala.
    score = MIN_SCORE + (MAX_SCORE - MIN_SCORE) * scale
    
    return round(score, 3)

def calculate_updated_trust(
    last_trust: float,
    direct_trust: float,
    indirect_trust: float,
    centrality_score: float,
    centrality_raw: int
) -> float:
    
    td = last_trust + direct_trust

    if indirect_trust is not None and indirect_trust > 0:
        t_updated = (0.4 * td) + (0.3 * indirect_trust) + (0.3 * centrality_score)
    else:
        if centrality_raw <= 1:
            t_updated = (0.7 * td) + (0.3 * centrality_score)
        else:
            t_updated = (0.4 * td) + (0.3 * indirect_trust) + (0.3 * centrality_score)
    return min(max(round(t_updated, 3), 0.0), 1.0)

def should_blacklist(trust_score: float, threshold: float = 0.3) -> bool:
    return trust_score < threshold

def get_flooding_threshold(is_coordinator: bool, device_count: int = 0) -> int:
    return 24 if is_coordinator else 12

def evaluate_flooding_risk(recent_connections: int, is_coordinator: bool, device_count: int = 0) -> dict:
    threshold = get_flooding_threshold(is_coordinator, device_count)
    
    if recent_connections > threshold:
        # Flooding detected - hanya penalty
        overflow_ratio = recent_connections / threshold
        penalty = min(0.2, 0.05 * overflow_ratio)  # Max penalty 0.2
        
        return {
            "penalty": penalty,
            "threshold": threshold
        }
    else:
        # Normal
        return {
            "penalty": 0.0,
            "threshold": threshold
        }
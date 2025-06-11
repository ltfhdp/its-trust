from enum import Enum

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

def calculate_updated_trust(
    last_trust: float,
    direct_trust: float,
    indirect_trust: float,
    centrality_score: float,
) -> float:
    
    td = last_trust + direct_trust

    if indirect_trust is not None and indirect_trust > 0:
        t_updated = (0.4 * td) + (0.3 * indirect_trust) + (0.3 * centrality_score)
    else:
        t_updated = (0.7 * td) + (0.3 * centrality_score)
    return min(max(round(t_updated, 3), 0.0), 1.0)

def should_blacklist(trust_score: float, threshold: float = 0.3) -> bool:
    return trust_score < threshold

# Update untuk logic.py - tambahkan fungsi flooding detection

def get_flooding_threshold(is_coordinator: bool, device_count: int = 0) -> int:
    """
    Hitung threshold flooding berdasarkan role device
    
    Args:
        is_coordinator: True jika device adalah coordinator
        device_count: Jumlah device aktif dalam network (untuk scaling)
    
    Returns:
        int: Maximum connections per time window
    """
    
    if is_coordinator:
        # Coordinator perlu interaksi dengan banyak device
        # Base: 30 connections, scale dengan jumlah device
        base_threshold = 30
        
        # Scale berdasarkan network size (max 2x base)
        if device_count > 10:
            scaling_factor = min(2.0, 1 + (device_count - 10) / 20)
            return int(base_threshold * scaling_factor)
        
        return base_threshold
    
    else:
        # Member node: aktivitas lebih terbatas
        # Base: 15 connections (interaksi dengan coordinator + beberapa peer)
        base_threshold = 15
        
        # Slight scaling untuk network besar
        if device_count > 20:
            scaling_factor = min(1.5, 1 + (device_count - 20) / 40)
            return int(base_threshold * scaling_factor)
            
        return base_threshold

def evaluate_flooding_risk(
    recent_connections: int, 
    is_coordinator: bool, 
    device_count: int = 0,
    time_window_seconds: int = 60
) -> dict:
    """
    Evaluasi risiko flooding dengan threshold adaptif
    
    Args:
        recent_connections: Jumlah koneksi dalam time window
        is_coordinator: Apakah device adalah coordinator
        device_count: Jumlah device aktif
        time_window_seconds: Window waktu (default 60 detik)
    
    Returns:
        dict: {
            "is_flooding": bool,
            "threshold": int, 
            "penalty": float,
            "risk_level": str
        }
    """
    
    threshold = get_flooding_threshold(is_coordinator, device_count)
    
    # Hitung rasio overflow
    overflow_ratio = recent_connections / threshold
    
    # Tentukan risk level dan penalty
    if overflow_ratio <= 0.8:
        # Normal activity
        return {
            "is_flooding": False,
            "threshold": threshold,
            "penalty": 0.0,
            "risk_level": "normal"
        }
    
    elif overflow_ratio <= 1.0:
        # Warning level - mendekati threshold
        return {
            "is_flooding": False,
            "threshold": threshold,
            "penalty": 0.02,  # Penalty kecil sebagai warning
            "risk_level": "warning"
        }
    
    elif overflow_ratio <= 1.5:
        # Flooding detected - moderate
        penalty = 0.05 + (overflow_ratio - 1.0) * 0.1  # 0.05 - 0.1
        return {
            "is_flooding": True,
            "threshold": threshold,
            "penalty": min(penalty, 0.15),
            "risk_level": "moderate"
        }
    
    else:
        # Severe flooding
        return {
            "is_flooding": True,
            "threshold": threshold,
            "penalty": 0.2,  # Max penalty
            "risk_level": "severe"
        }
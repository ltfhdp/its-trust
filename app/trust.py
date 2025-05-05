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
        "Computer": 0.8,
        "Smartphone": 0.6,
        "Smart Device": 0.4,
        "Sensor": 0.2,
        "RFID": 0.1
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

def calculate_initial_trust(ownership_type: str, memory_gb: float) -> float:
    if ownership_type.lower() == "internal":
        mem_weight = get_memory_weight(memory_gb)
        comp_weight = get_computing_weight("RSU")  # default RSU for internal
        return round((mem_weight + comp_weight) / 2, 3)
    else:
        return 0.5

def get_direct_trust_score(success: bool) -> float:
    return 0.1 if success else -0.1

def calculate_updated_trust(
    last_trust: float,
    direct_trust: float,
    indirect_trust: float,
    centrality_score: float,
) -> float:
    w0, w1, w2, w3 = 0.2, 0.5, 0.2, 0.1

    td = last_trust + direct_trust
    t_updated = (w0 * last_trust) + (w1 * td) + (w2 * indirect_trust) + (w3 * centrality_score)
    return max(0.0, min(1.0, round(t_updated, 3)))

def should_blacklist(trust_score: float, threshold: float = 0.3) -> bool:
    return trust_score < threshold

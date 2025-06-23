import requests
import random
import time
import os

BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
TOTAL_DEVICES = 10
MALICIOUS_PERCENT = 0.25
DEVICE_BEHAVIOR = {
    "RSU": ["propagate_info", "sync_trust"],
    "Smartphone": ["send_location", "ping_rsu"],
    "Computer": ["query_info", "request_update"],
    "Sensor": ["send_status"],
    "Smart Device": ["request_update"],
    "RFID": ["send_identity"]
}
            
def get_all_devices():
    try:
        res = requests.get(f"{BASE_URL}/devices/")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        print(f"❌ Error getting all devices: {e}")
    return []
    
def get_coordinator_id():
    try:
        res = requests.get(f"{BASE_URL}/coordinator")
        return res.json()["id"] if res.status_code == 200 else None
    except Exception:
        return None

def get_reputation(device_id: str):
    try:
        res = requests.get(f"{BASE_URL}/reputation/{device_id}")
        if res.status_code == 200:
            return res.json()
    except Exception as e:
        pass
    return {"exists": False}

def register_device(device_id, device_type=None, ownership_type=None):
    if not device_type:
        device_type = random.choice(list(DEVICE_BEHAVIOR.keys()))
    if not ownership_type:
        ownership_type = "internal" if device_type == "RSU" else random.choice(["internal", "external"])
        
    payload = {
        "id": device_id,
        "name": f"{device_type}-{device_id}",
        "ownership_type": ownership_type,
        "device_type": device_type,
        "memory_gb": random.choice([2, 4, 8]),
        "location": random.choice(["A", "B", "C"])
    }
    try:
        res = requests.post(f"{BASE_URL}/device", json=payload)
        if res.status_code == 200:
            print(f"📥  Register OK: {device_id} ({device_type})")
            return res.json()
        elif res.status_code == 403: # rejoin failed
            print(f"⚠️  Rejoin FAILED: {device_id} - {res.json().get('detail')}")
            return None
        else:
            print(f"❌  Register FAIL: {device_id} - {res.status_code} {res.text}")
            return None
    except Exception as e:
        print(f"💥  ERROR registering {device_id}: {e}")
        return None

def initialize_devices(total=TOTAL_DEVICES, malicious_ratio=MALICIOUS_PERCENT):
    device_ids = [f"dev-{i:03}" for i in range(total)]
    malicious_count = int(total * malicious_ratio)
    
    # RSU selalu device normal di awal untuk fondasi jaringan
    rsu_ids = [dev_id for dev_id in device_ids[:3]]
    for dev_id in rsu_ids:
        register_device(dev_id, device_type="RSU", ownership_type="internal")
    
    other_devices = device_ids[3:]
    for dev_id in other_devices:
        register_device(dev_id)

    # pilih device jahat dari non-RSU
    malicious_ids = set(random.sample(other_devices, min(malicious_count, len(other_devices))))
    
    print("\n" + "="*50)
    print("🛡️  DEVICE CLASSIFICATION")
    print("="*50)
    for dev_id in device_ids:
        status = "🔴 MALICIOUS" if dev_id in malicious_ids else "🟢 NORMAL"
        print(f"{dev_id}: {status}")
        
    return device_ids, malicious_ids

def create_connection(src, tgt, success=True):
    payload = {
        "device_id": src,
        "connected_device_id": tgt,
        "status": success,
        "connection_type": "data_exchange"
    }
    try:
        res = requests.post(f"{BASE_URL}/connect", json=payload)
        status_icon = "✅" if success else "❌"
    except Exception as e:
        print(f"💥 ERROR creating connection: {e}")

def rate_peer(rater, target, score):
    payload = { "rater_device_id": rater, "rated_device_id": target, "score": score }
    try:
        res = requests.post(f"{BASE_URL}/rate_peer/", json=payload)
        # print(f"  ⭐ {rater} rates {target} with {score:.1f} -> {res.status_code}")
    except Exception as e:
        print(f"💥 ERROR rating peer: {e}")

def simulate_interaction(src, tgt, success):
    # 1. Buat koneksi
    create_connection(src, tgt, success=success)
    
    # 2. Lakukan rating dua arah berdasarkan hasil koneksi
    if success:
        # Jika berhasil, rating tinggi dari kedua belah pihak
        score_src_to_tgt = round(random.uniform(0.8, 1.0), 2)
        score_tgt_to_src = round(random.uniform(0.8, 1.0), 2)
    else:
        # Jika gagal, rating rendah dari kedua belah pihak
        score_src_to_tgt = round(random.uniform(0.0, 0.3), 2)
        score_tgt_to_src = round(random.uniform(0.0, 0.3), 2)
        
    rate_peer(src, tgt, score_src_to_tgt)
    rate_peer(tgt, src, score_tgt_to_src)
        
def leave_device(device_id):
    try:
        res = requests.post(f"{BASE_URL}/device/{device_id}/leave")
        if res.status_code == 200:
            print(f"🚪  Device {device_id} has left the network.")
        else:
            print(f"⚠️  Device {device_id} failed to leave: {res.json().get('detail')}")
    except Exception as e:
        print(f"💥 ERROR leaving device: {e}")
import requests
import random
import time

BASE_URL = "http://localhost:8000"
TOTAL_DEVICES = 10
ITERATIONS = 3
ACTIONS_PER_ITER = 25
MALICIOUS_PERCENT = 0.2

device_ids = []
malicious_ids = set()
coordinator_id = None

DEVICE_BEHAVIOR = {
    "RSU": ["propagate_info", "sync_trust"],
    "Smartphone": ["send_location", "ping_rsu"],
    "Computer": ["query_info", "request_update"],
    "Sensor": ["send_status"],
    "Smart Device": ["request_update"],
    "RFID": ["send_identity"]
}

def is_device_registered(device_id):
    try:
        res = requests.get(f"{BASE_URL}/device/{device_id}")
        return res.status_code == 200
    except:
        return False

def get_device_type(device_id):
    try:
        res = requests.get(f"{BASE_URL}/device/{device_id}")
        if res.status_code == 200:
            return res.json().get("device_type")
    except:
        pass
    return random.choice(list(DEVICE_BEHAVIOR.keys()))

def get_coordinator_id():
    try:
        res = requests.get(f"{BASE_URL}/coordinator")
        if res.status_code == 200:
            return res.json()["id"]
    except:
        pass
    return None

def register_device(device_id):
    if is_device_registered(device_id):
        print(f"🔄 Skip register: {device_id} already exists.")
        return get_device_type(device_id)

    device_type = random.choice(list(DEVICE_BEHAVIOR.keys()))
    ownership_type = "internal" if device_type == "RSU" else random.choice(["internal", "external"])
    payload = {
        "id": device_id,
        "name": f"{device_type}-{device_id}",
        "ownership_type": ownership_type,
        "device_type": device_type,
        "memory_gb": random.choice([1, 2, 4, 8]),
        "location": random.choice(["A", "B", "C"])
    }
    try:
        res = requests.post(f"{BASE_URL}/device", json=payload)
        print(f"📥 Register {device_id}: {res.status_code} ({device_type})")
        return device_type
    except Exception as e:
        print(f"❌ Error register {device_id}: {e}")
        return None

def connect_devices(src, tgt, connection_type="data", success=True):
    payload = {
        "device_id": src,
        "connected_device_id": tgt,
        "status": success,
        "connection_type": connection_type
    }
    try:
        res = requests.post(f"{BASE_URL}/connect", json=payload)
        print(f"{src} ➡️ {tgt} | {connection_type}, success={success} → {res.status_code}")
    except Exception as e:
        print(f"Connect error: {e}")

def rate_peer(rater, target, connection_success=True, is_malicious_rater=False):
    """Simplified peer rating logic for MVP"""
    
    # Malicious device behavior - badmouthing attack
    if is_malicious_rater:
        if target in malicious_ids:
            # Malicious rating malicious = tinggi (kolusi)
            score = round(random.uniform(0.8, 1.0), 2)
        else:
            # Malicious rating normal = rendah (badmouthing)
            score = round(random.uniform(0.1, 0.3), 2)
    else:
        # Normal device behavior
        if target in malicious_ids:
            # Normal rating malicious = rendah (deteksi benar)
            score = round(random.uniform(0.1, 0.4), 2)
        else:
            # Normal rating normal = tinggi berdasarkan koneksi
            if connection_success:
                score = round(random.uniform(0.7, 1.0), 2)
            else:
                score = round(random.uniform(0.3, 0.6), 2)

    payload = {
        "rater_device_id": rater,
        "rated_device_id": target,
        "score": score,
        "comment": f"auto-rating ({'malicious' if is_malicious_rater else 'normal'} rater)"
    }
    try:
        res = requests.post(f"{BASE_URL}/rate_peer/", json=payload)
        malicious_flag = "🔴" if is_malicious_rater else "🟢"
        target_flag = "🔴" if target in malicious_ids else "🟢"
        print(f"⭐ {malicious_flag}{rater} → {target_flag}{target} = {score} → {res.status_code}")
    except Exception as e:
        print(f"Rating error: {e}")

def simulate_activity(src_id, src_type, all_devices):
    """Updated simulate_activity dengan peer rating yang lebih realistis"""
    global coordinator_id

    behavior = random.choice(DEVICE_BEHAVIOR.get(src_type, ["send_status"]))
    potential_targets = [d for d in all_devices if d != src_id]
    is_malicious_src = src_id in malicious_ids

    if behavior == "propagate_info":
        targets = random.sample(potential_targets, min(3, len(potential_targets)))
        for tgt in targets:
            success = not is_malicious_src  # Malicious device bikin koneksi gagal
            connect_devices(src_id, tgt, connection_type="info", success=success)
            
            # Peer rating - hanya kadang-kadang, tidak setiap koneksi
            if random.random() < 0.3:  # 30% chance rating
                rate_peer(src_id, tgt, connection_success=success, is_malicious_rater=is_malicious_src)
                rate_peer(tgt, src_id, connection_success=success, is_malicious_rater=(tgt in malicious_ids))

    elif behavior == "ping_rsu":
        rsu_targets = [d for d in potential_targets if "RSU" in get_device_type(d)]
        if rsu_targets:
            tgt = random.choice(rsu_targets)
            success = not is_malicious_src
            connect_devices(src_id, tgt, connection_type="ping", success=success)
            
            if random.random() < 0.2:  # 20% chance rating untuk ping
                rate_peer(src_id, tgt, connection_success=success, is_malicious_rater=is_malicious_src)

    elif behavior == "send_location":
        tgt = coordinator_id if coordinator_id else random.choice(potential_targets)
        success = not is_malicious_src
        connect_devices(src_id, tgt, connection_type="location", success=success)
        
        if random.random() < 0.25:  # 25% chance rating
            rate_peer(src_id, tgt, connection_success=success, is_malicious_rater=is_malicious_src)

    elif behavior == "sync_trust":
        tgt = random.choice(potential_targets)
        success = not is_malicious_src
        connect_devices(src_id, tgt, connection_type="sync", success=success)
        
        if random.random() < 0.4:  # 40% chance rating untuk sync trust
            rate_peer(src_id, tgt, connection_success=success, is_malicious_rater=is_malicious_src)
            rate_peer(tgt, src_id, connection_success=success, is_malicious_rater=(tgt in malicious_ids))

    elif behavior in ["query_info", "request_update", "send_status", "send_identity"]:
        tgt = random.choice(potential_targets)
        success = not is_malicious_src
        connect_devices(src_id, tgt, connection_type=behavior, success=success)
        
        if random.random() < 0.15:  # 15% chance rating untuk aktivitas biasa
            rate_peer(src_id, tgt, connection_success=success, is_malicious_rater=is_malicious_src)

def simulate_activity(src_id, src_type, all_devices):
    global coordinator_id

    behavior = random.choice(DEVICE_BEHAVIOR.get(src_type, ["send_status"]))
    potential_targets = [d for d in all_devices if d != src_id]

    if behavior == "propagate_info":
        targets = random.sample(potential_targets, min(3, len(potential_targets)))
        for tgt in targets:
            connect_devices(src_id, tgt, connection_type="info", success=True)
            rate_peer(src_id, tgt, connection_success=True)
            rate_peer(tgt, src_id, connection_success=True)

    elif behavior == "ping_rsu":
        rsu_targets = [d for d in potential_targets if d.startswith("RSU") or "RSU" in d]
        if rsu_targets:
            tgt = random.choice(rsu_targets)
            connect_devices(src_id, tgt, connection_type="ping", success=True)
            rate_peer(src_id, tgt, connection_success=True)
            rate_peer(tgt, src_id, connection_success=True)


    elif behavior == "send_location":
        tgt = coordinator_id or random.choice(potential_targets)
        connect_devices(src_id, tgt, connection_type="location", success=True)
        rate_peer(src_id, tgt, connection_success=True)
        rate_peer(tgt, src_id, connection_success=True)

    elif behavior == "sync_trust":
        tgt = random.choice(potential_targets)
        connect_devices(src_id, tgt, connection_type="sync", success=True)
        rate_peer(src_id, tgt, connection_success=True)
        rate_peer(tgt, src_id, connection_success=True)

    elif behavior in ["query_info", "request_update", "send_status", "send_identity"]:
        tgt = random.choice(potential_targets)
        connect_devices(src_id, tgt, connection_type=behavior, success=True)
        rate_peer(src_id, tgt, connection_success=True)
        rate_peer(tgt, src_id, connection_success=True)

def run_simulation():
    global coordinator_id, device_ids, malicious_ids

    print("🚀 Starting ITS Trust System Simulation...")
    print(f"📊 Total devices: {TOTAL_DEVICES}, Malicious: {int(TOTAL_DEVICES * MALICIOUS_PERCENT)}")
    
    # Register devices
    device_types = {}
    for i in range(TOTAL_DEVICES):
        dev_id = f"dev-{i:03}"
        device_ids.append(dev_id)
        device_types[dev_id] = register_device(dev_id)
        time.sleep(0.01)

    # Select malicious devices
    malicious_ids = set(random.sample(device_ids, int(TOTAL_DEVICES * MALICIOUS_PERCENT)))
    
    print("\n" + "="*50)
    print("🛡️  DEVICE CLASSIFICATION")
    print("="*50)
    for dev_id in device_ids:
        status = "🔴 MALICIOUS" if dev_id in malicious_ids else "🟢 NORMAL"
        dev_type = device_types.get(dev_id, "Unknown")
        print(f"{dev_id}: {status} ({dev_type})")
    
    time.sleep(1)
    coordinator_id = get_coordinator_id()
    coord_status = "🔴 MALICIOUS COORD!" if coordinator_id in malicious_ids else "🟢 Safe"
    print(f"\n👑 Coordinator: {coordinator_id} {coord_status}")
    
    print(f"\n🎬 Starting {ITERATIONS} iterations with {ACTIONS_PER_ITER} actions each...")
    
    for i in range(ITERATIONS):
        print(f"\n{'='*20} Iteration {i+1} {'='*20}")
        
        # Simulasi berbagai jenis attack
        for action_num in range(ACTIONS_PER_ITER):
            src = random.choice(device_ids)
            src_type = device_types.get(src, "Sensor")
            
            if src in malicious_ids:
                # Malicious behavior - flooding attack
                if random.random() < 0.7:  # 70% flooding
                    for _ in range(random.randint(2, 5)):  # Burst connections
                        tgt = random.choice([d for d in device_ids if d != src])
                        connect_devices(src, tgt, connection_type="flood", success=False)
                        time.sleep(0.01)
                        
                        # Badmouthing attack
                        if random.random() < 0.3:
                            rate_peer(src, tgt, connection_success=False, is_malicious_rater=True)
                else:
                    simulate_activity(src, src_type, device_ids)
            else:
                # Normal behavior
                simulate_activity(src, src_type, device_ids)

            time.sleep(0.1)
        
        # Check coordinator status setelah setiap iterasi
        new_coordinator = get_coordinator_id()
        if new_coordinator != coordinator_id:
            old_status = "🔴" if coordinator_id in malicious_ids else "🟢"
            new_status = "🔴" if new_coordinator in malicious_ids else "🟢"
            print(f"👑 COORDINATOR CHANGE: {old_status}{coordinator_id} → {new_status}{new_coordinator}")
            coordinator_id = new_coordinator
        
        print(f"✅ Iteration {i+1} complete")
    
    print("\n🏁 Simulation completed!")
    print("📈 Check /log_activity endpoint for detailed results")

if __name__ == "__main__":
    run_simulation()
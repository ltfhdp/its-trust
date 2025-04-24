import requests
import random
import time

API_BASE = "http://localhost:8000"

devices = [
    {"id": "rsu-1", "name": "RSU Utama", "ownership_type": "internal", "device_type": "RSU", "memory_gb": 16, "location": "Jalan Utama"},
    {"id": "sensor-1", "name": "Sensor Kecepatan 1", "ownership_type": "external", "device_type": "Sensor", "memory_gb": 2, "location": "Gerbang Barat"},
    {"id": "sensor-2", "name": "Sensor Suhu", "ownership_type": "external", "device_type": "Sensor", "memory_gb": 1, "location": "Pintu Timur"},
    {"id": "cam-1", "name": "Kamera CCTV A", "ownership_type": "external", "device_type": "Smart Device", "memory_gb": 4, "location": "Pasar Minggu"},
    {"id": "phone-1", "name": "User Smartphone", "ownership_type": "external", "device_type": "Smartphone", "memory_gb": 6, "location": "Dekat RS"}
]

def register_all_devices():
    for device in devices:
        res = requests.post(f"{API_BASE}/device/", json=device)
        print(f"Registered {device['id']}: {res.status_code}")
        time.sleep(0.1)

def simulate_interactions(num_interactions=50):
    print("\nSimulating normal interactions...\n")
    device_ids = [d["id"] for d in devices]
    for _ in range(num_interactions):
        a, b = random.sample(device_ids, 2)
        status = random.choices([True, False], weights=[0.85, 0.15])[0]  # mostly success
        res = requests.post(f"{API_BASE}/connect/", json={
            "device_id": a,
            "connected_device_id": b,
            "status": status
        })
        print(f"{a} → {b}: {'✔' if status else '✘'} ({res.status_code})")
        time.sleep(0.1)

def simulate_attack(from_device, targets=None, times=15):
    print("\nSimulating attack scenario...\n")
    if targets is None:
        targets = [d["id"] for d in devices if d["id"] != from_device]
    for _ in range(times):
        target = random.choice(targets)
        res = requests.post(f"{API_BASE}/connect/", json={
            "device_id": from_device,
            "connected_device_id": target,
            "status": False  # always fail
        })
        print(f"{from_device} → {target}: ✘ attack ({res.status_code})")
        time.sleep(0.1)

def simulate_behavioral_attacker(device_id, targets, fail_rate=1.0, times=20):
    print(f"\n{device_id} acting suspiciously...\n")
    for _ in range(times):
        target = random.choice(targets)
        status = random.random() > fail_rate  # mostly fail
        res = requests.post(f"{API_BASE}/connect/", json={
            "device_id": device_id,
            "connected_device_id": target,
            "status": status
        })
        print(f"{device_id} → {target}: {'✔' if status else '✘'} ({res.status_code})")
        time.sleep(0.1)

def show_device_summary():
    print("\nCurrent Device Trust States:\n")
    res = requests.get(f"{API_BASE}/devices/")
    for d in res.json():
        print(f"{d['id']} | Trust: {d['trust_score']:.3f} | Blacklisted: {d['is_blacklisted']} | Coordinator: {d['is_coordinator']}")

def list_suspicious_devices():
    res = requests.get(f"{API_BASE}/devices/")
    print("\nSuspicious Devices (Blacklisted or Low Trust):")
    for d in res.json():
        if d["is_blacklisted"] or d["trust_score"] < 0.4:
            print(f"{d['id']} | Trust: {d['trust_score']} | Blacklisted: {d['is_blacklisted']}")

def show_device_history(device_id):
    print(f"\nTrust History for {device_id}:")
    res = requests.get(f"{API_BASE}/device/{device_id}/history")
    for h in res.json():
        print(f"{h['timestamp']} | Trust: {h['trust_score']:.3f} | Notes: {h['notes']}")

def show_all_device_histories():
    for d in devices:
        show_device_history(d["id"])
        print("-" * 40)

def show_coordinator():
    res = requests.get(f"{API_BASE}/coordinator")
    print("\nCurrent Coordinator:")
    print(f"{res.json()['id']} - {res.json()['name']}")

if __name__ == "__main__":
    register_all_devices()
    simulate_interactions(40)
    simulate_behavioral_attacker("cam-1", targets=[d["id"] for d in devices if d["id"] != "cam-1"], fail_rate=0.9)
    show_device_summary()
    list_suspicious_devices()
    show_all_device_histories()
    show_coordinator()

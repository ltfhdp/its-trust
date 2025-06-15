# test_scenario_1_normal.py
import random
import time
from test_utils import (
    reset_database, initialize_devices, simulate_interaction, # Ganti create_connection dengan simulate_interaction
    leave_device, register_device, get_all_devices
)

def run_simulation():
    print("🚀 SCENARIO 1: NORMAL LIFECYCLE (with mandatory peer rating)")
    reset_database()
    
    # 1. Inisialisasi device, semua normal
    all_ids, _ = initialize_devices(total=10, malicious_ratio=0)
    
    # 2. Simulasi interaksi normal menggunakan fungsi baru
    print("\n🔄 --- Simulating normal interactions with 2-way ratings ---")
    for i in range(3):
        print(f"\n--- Iteration {i+1} ---")
        for _ in range(15):
            src, tgt = random.sample(all_ids, 2)
            simulate_interaction(src, tgt, success=True) # <-- GUNAKAN FUNGSI BARU
        time.sleep(0.1)
        
    devices = get_all_devices()
    print("\nTrust scores after normal interaction:")
    for dev in devices:
        print(f"- {dev['id']}: {dev['trust_score']:.3f}")

    # 3. Satu device keluar jaringan
    device_to_leave = random.choice(all_ids)
    leave_device(device_to_leave)
    
    # 4. Device yang keluar mencoba bergabung kembali
    print(f"\n↩️  Device {device_to_leave} trying to rejoin...")
    time.sleep(0.5)
    register_device(device_to_leave)

    # 5. Simulasi device 'bermasalah' yang sering gagal koneksi
    flaky_device = random.choice([d for d in all_ids if d != device_to_leave])
    print(f"\n📉 --- Simulating a 'flaky' device ({flaky_device}) with 2-way ratings ---")
    for i in range(5):
        print(f"\n--- Flaky Iteration {i+1} ---")
        for _ in range(10):
            src, tgt = random.sample(all_ids, 2)
            is_flaky_involved = flaky_device in [src, tgt]
            success = not (is_flaky_involved and random.random() < 0.7)
            simulate_interaction(src, tgt, success=success) # <-- GUNAKAN FUNGSI BARU DI SINI JUGA
        time.sleep(2.0)

    devices = get_all_devices()
    print("\nTrust scores after flaky device simulation:")
    # ... (sisa kode tidak perlu diubah) ...
    flaky_final_trust = 0
    for dev in devices:
        if dev['id'] == flaky_device:
            flaky_final_trust = dev['trust_score']
            print(f"- {dev['id']}: {dev['trust_score']:.3f} (Flaky Device)")
        else:
            print(f"- {dev['id']}: {dev['trust_score']:.3f}")

    # 6. Device 'bermasalah' keluar dan mencoba rejoin
    leave_device(flaky_device)
    print(f"\n🤔 Flaky device {flaky_device} (trust: {flaky_final_trust:.3f}) trying to rejoin...")
    time.sleep(1)
    register_device(flaky_device)

    print("\n🏁 SCENARIO 1 COMPLETE")

if __name__ == "__main__":
    run_simulation()
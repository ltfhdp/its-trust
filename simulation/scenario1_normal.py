import random
import time
from test_utils import (
    initialize_devices, create_connection, rate_peer, get_reputation,
    leave_device, register_device, get_all_devices
)

def calculate_smart_score(target_id: str, connection_success: bool) -> float:
    target_reputation = get_reputation(target_id)
    
    if not target_reputation or not target_reputation.get("exists"):
        return 0.5

    if connection_success:
        base_score = random.uniform(0.7, 1.0)
    else:
        base_score = random.uniform(0.1, 0.4)
        
    reputation_level = target_reputation.get("reputation_level", "AVERAGE")
        
    if reputation_level == "BLACKLISTED":
        adjusted_score = min(base_score, 0.1)
    elif reputation_level == "VERY_SUSPICIOUS":
        adjusted_score = min(base_score, 0.15)
    elif reputation_level == "SUSPICIOUS":
        adjusted_score = min(base_score, random.uniform(0.3, 0.5))
    else: 
        adjusted_score = base_score
        
    return round(max(0.0, min(1.0, adjusted_score)), 2)


def run_simulation():
    print("SCENARIO 1: NORMAL INTERACTIONS")
    
    all_ids, _ = initialize_devices(total=10, malicious_ratio=0)
    
    print("\n🔄 --- Simulating 50 interactions ---")
    for i in range(100):
        src, tgt = random.sample(all_ids, 2)
        success = random.random() < 0.9 
        status_str = "OK" if success else "FAIL"

        # 1. Catat koneksi
        create_connection(src, tgt, success=success)

        
        # 2. Hitung skor rating berdasarkan keberhasilan
        score_src_to_tgt = calculate_smart_score(tgt, connection_success=success)
        score_tgt_to_src = calculate_smart_score(src, connection_success=success)

        # 3. Lakukan rating dua arah
        rate_peer(src, tgt, score_src_to_tgt)
        rate_peer(tgt, src, score_tgt_to_src)
        
        print(f"  -> Iter {i+1}: {src} <-> {tgt} ({status_str}) | Ratings: {score_src_to_tgt:.2f} / {score_tgt_to_src:.2f}")

    devices = get_all_devices()
    print("\nTrust scores after initial interactions:")
    for dev in devices:
        print(f"- {dev['id']}: {dev['trust_score']:.3f}")

    # 3. Satu device keluar jaringan secara acak
    device_to_leave = random.choice(all_ids)
    print(f"\nDevice {device_to_leave} is leaving...")
    leave_device(device_to_leave)
    
    # 4. Device yang keluar mencoba bergabung kembali
    print(f"Device {device_to_leave} is trying to rejoin...")
    time.sleep(1)
    register_device(device_to_leave)

    print("\n\n" + "="*50)
    print("FINAL SYSTEM STATUS")
    print("="*50)
    
    
    devices = get_all_devices()
    for dev in sorted(devices, key=lambda x: x['id']):
        print(f"- {dev['id']}: {dev['trust_score']:.3f}")

    print("\nSCENARIO 1 COMPLETE")

if __name__ == "__main__":
    run_simulation()
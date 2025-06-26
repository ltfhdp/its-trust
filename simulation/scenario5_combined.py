import random
import time
from test_utils import (
    initialize_devices, create_connection,
    rate_peer, get_coordinator_id, get_all_devices,
    get_reputation
)

def calculate_smart_score(target_id: str, connection_success: bool) -> float:
    target_reputation = get_reputation(target_id)
    
    if not target_reputation or not target_reputation.get("exists"):
        return 0.5

    if connection_success:
        base_score = random.uniform(0.7, 1.0)
    else:
        # Jika koneksi gagal, skor dasar akan rendah
        base_score = random.uniform(0.1, 0.4)
        
    reputation_level = target_reputation.get("reputation_level", "AVERAGE")
        
    if reputation_level == "BLACKLISTED":
        adjusted_score = min(base_score, 0.1)
    elif reputation_level == "VERY_SUSPICIOUS":
        adjusted_score = min(base_score, 0.15)
    elif reputation_level == "SUSPICIOUS":
        adjusted_score = min(base_score, random.uniform(0.3, 0.5))
    elif reputation_level == "POOR":
        adjusted_score = base_score * 0.9
    else: 
        adjusted_score = base_score
        
    return round(max(0.0, min(1.0, adjusted_score)), 2)


def run_simulation():
    print(" SCENARIO: COMBINED ATTACK")
    
    all_ids, malicious_ids = initialize_devices(total=25, malicious_ratio=0.3)
    
    print(f"\n Initial Coordinator: {get_coordinator_id()}")
    print(f"Malicious: {len(malicious_ids)} devices")
    
    print("\n --- Simulating combined attacks ---")
    for i in range(10):
        print(f"\n--- Iteration {i+1} | Coordinator: {get_coordinator_id()} ---")
        
        for src in all_ids:
            # Perilaku device normal
            if src not in malicious_ids:
                target = random.choice([d for d in all_ids if d != src])

                is_successful = random.random() < 0.9  # 90% kemungkinan berhasil
                status_str = "SUCCESS" if is_successful else "FAIL"
                
                create_connection(src, target, success=is_successful)
                print(f"  ->  {src} (normal) interacts with {target} -> {status_str}")

                # Rating dari src ke target, berdasarkan status koneksi
                score_from_src = calculate_smart_score(target, connection_success=is_successful)
                rate_peer(src, target, score_from_src)
                
                # Rating balasan dari target ke src
                if target in malicious_ids:
                    # Perangkat jahat selalu membalas dengan fitnah
                    score_from_target = round(random.uniform(0.1, 0.3), 2)
                    print(f"  ->    {target} (malicious) badmouths {src} back!")
                    rate_peer(target, src, score_from_target)
                else:
                    # Perangkat normal membalas berdasarkan status koneksi yang sama
                    score_from_target = calculate_smart_score(src, connection_success=is_successful)
                    rate_peer(target, src, score_from_target)

            # Perilaku device jahat (acak)
            else:
                attack_type = random.choice(["flood", "badmouth"])
                
                if attack_type == "flood" and random.random() < 0.3:
                    print(f"  ->  {src} is flooding...")
                    for _ in range(5):
                        target = random.choice([d for d in all_ids if d != src])
                        create_connection(src, target, success=False)

                elif attack_type == "badmouth":
                    target = random.choice([d for d in all_ids if d not in malicious_ids and d != src])
                    
                    score_from_src = round(random.uniform(0.1, 0.3), 2)
                    print(f"  ->  {src} badmouths {target} with score {score_from_src}")
                    rate_peer(src, target, score_from_src)

                    # Balasan dari normal device (diasumsikan koneksi sukses dari sudut pandangnya)
                    score_from_target = calculate_smart_score(src, connection_success=True)
                    print(f"  ->    {target} (normal) smart-rates {src} back.")
                    rate_peer(target, src, score_from_target)
        
        time.sleep(1) 

    print("\n" + "="*50)
    print("FINAL SYSTEM STATUS")
    print("="*50)
    devices = get_all_devices()
    blacklisted_count = sum(1 for d in devices if d['is_blacklisted'])
    malicious_blacklisted = sum(1 for d in devices if d['id'] in malicious_ids and d['is_blacklisted'])
    
    print(f"Final Coordinator: {get_coordinator_id()}")
    print(f"Total Devices Blacklisted: {blacklisted_count} / {len(all_ids)}")
    print(f"Malicious Devices Caught: {malicious_blacklisted} / {len(malicious_ids)}")
    
    print("\n--- Detailed Trust Scores ---")
    for dev in sorted(devices, key=lambda x: x['id']):
        status = "🔴 MALICIOUS" if dev['id'] in malicious_ids else "🟢 NORMAL   "
        blacklisted = " - BLACKLISTED ☠️" if dev['is_blacklisted'] else ""
        print(f"- {dev['id']} ({status}): {dev['trust_score']:.3f}{blacklisted}")

    print("\n SCENARIO COMPLETE")

if __name__ == "__main__":
    run_simulation()
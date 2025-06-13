import random
import time
from test_utils import (
    reset_database, initialize_devices, create_connection,
    rate_peer, get_coordinator_id, get_all_devices
)

def run_simulation():
    print("🚀 SCENARIO 5: COMBINED ATTACK (CHAOS MODE)")
    reset_database()
    
    all_ids, malicious_ids = initialize_devices(total=25, malicious_ratio=0.3)
    
    print(f"\n👑 Initial Coordinator: {get_coordinator_id()}")
    print(f"Malicious: {len(malicious_ids)} devices")
    
    print("\n🔄 --- Simulating combined attacks ---")
    for i in range(10):
        print(f"\n--- Iteration {i+1} | Coordinator: {get_coordinator_id()} ---")
        
        for src in all_ids:
            # Perilaku device normal
            if src not in malicious_ids:
                target = random.choice([d for d in all_ids if d != src])
                create_connection(src, target, success=True)
                if random.random() < 0.2: # Sesekali memberi rating
                    rate_peer(src, target, round(random.uniform(0.8, 1.0), 2))
            
            # Perilaku device jahat (acak)
            else:
                attack_type = random.choice(["flood", "badmouth", "collude"])
                
                if attack_type == "flood" and random.random() < 0.3:
                    # FLOODING ATTACK (30% chance per iteration)
                    print(f"  -> 🌊 {src} is flooding...")
                    for _ in range(5):
                        target = random.choice([d for d in all_ids if d != src])
                        create_connection(src, target, success=False)

                elif attack_type == "badmouth":
                    # BADMOUTHING ATTACK
                    target = random.choice([d for d in all_ids if d not in malicious_ids and d != src])
                    score = round(random.uniform(0.1, 0.3), 2)
                    print(f"  -> 🗣️ {src} badmouths {target} with score {score}")
                    rate_peer(src, target, score)

                elif attack_type == "collude":
                    # COLLUSION (part of hijack)
                    target = random.choice(list(malicious_ids - {src}))
                    if target:
                        score = round(random.uniform(0.9, 1.0), 2)
                        print(f"  -> 🤝 {src} colludes with {target} with score {score}")
                        rate_peer(src, target, score)
        
        time.sleep(2)

    print("\n" + "="*50)
    print("📈 FINAL SYSTEM STATUS")
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

    print("\n🏁 SCENARIO 5 COMPLETE")
    print("Sistem yang tangguh akan berhasil mem-blacklist sebagian besar device jahat")
    print("dan mempertahankan koordinator yang sah (bukan device jahat).")

if __name__ == "__main__":
    run_simulation()
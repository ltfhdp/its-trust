# test_scenario_3_flooding.py
import random
import time
from test_utils import (
    reset_database, initialize_devices, create_connection, get_all_devices, simulate_interaction
)

def run_simulation():
    print("🚀 SCENARIO 3: FLOODING ATTACK")
    reset_database()
    
    all_ids, malicious_ids = initialize_devices(total=15, malicious_ratio=0.2)
    flooder = random.choice(list(malicious_ids))
    
    print(f"\nATTACKER (Flooder): {flooder}")
    
    print("\n🔄 --- Simulating normal traffic, then a flood attack ---")
    for i in range(5):
        print(f"\n--- Iteration {i+1} ---")
        
        # 1. Fase Serangan Flooding oleh si penyerang
        if i == 2: # Serangan dimulai di iterasi ke-3
            print(f"🌊🌊🌊 FLOODING ATTACK INITIATED BY {flooder} 🌊🌊🌊")
            targets = [d for d in all_ids if d != flooder]
            for _ in range(30): # Kirim 30 permintaan koneksi secara cepat
                target = random.choice(targets)
                simulate_interaction(flooder, target, success=False)
    
                time.sleep(0.05)
            print(f"🌊🌊🌊 FLOODING ATTACK COMPLETE 🌊🌊🌊")

        # 2. Aktivitas normal oleh device lain
        for src in all_ids:
            if src != flooder:
                target = random.choice([d for d in all_ids if d != src])
                simulate_interaction(src, target, success=True)
        
        time.sleep(1)

    print("\n" + "="*50)
    print("📈 FINAL TRUST SCORES")
    print("="*50)
    devices = get_all_devices()
    for dev in sorted(devices, key=lambda x: x['id']):
        status = "🔴 MALICIOUS" if dev['id'] in malicious_ids else "🟢 NORMAL   "
        is_flooder = "(ATTACKER)" if dev['id'] == flooder else ""
        blacklisted = " - BLACKLISTED ☠️" if dev['is_blacklisted'] else ""
        print(f"- {dev['id']} {is_flooder} ({status}): {dev['trust_score']:.3f}{blacklisted}")

    print("\n🏁 SCENARIO 3 COMPLETE")
    print("Perhatikan bagaimana trust device ATTACKER turun drastis dan kemungkinan besar di-blacklist.")

if __name__ == "__main__":
    run_simulation()
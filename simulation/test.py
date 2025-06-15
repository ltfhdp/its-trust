import random
import time
from test_utils import (
    reset_database, initialize_devices, create_connection,
    rate_peer, get_all_devices, get_reputation, register_device, leave_device
)

def calculate_smart_score(target_id: str, connection_success: bool) -> float:
    """Memberikan rating cerdas berdasarkan info reputasi dari API."""
    target_reputation = get_reputation(target_id)
    if not target_reputation or not target_reputation.get("exists"): return 0.5
    
    base_score = random.uniform(0.7, 1.0) if connection_success else random.uniform(0.1, 0.4)
    level = target_reputation.get("reputation_level", "AVERAGE")

    if level == "BLACKLISTED": return min(base_score, 0.1)
    if level == "VERY_SUSPICIOUS": return min(base_score, 0.15)
    if level == "SUSPICIOUS": return min(base_score, random.uniform(0.3, 0.5))
    if level == "POOR": return base_score * 0.9
    return round(max(0.0, min(1.0, base_score)), 2)

def run_simulation():
    print("🚀 SCENARIO: Integrated Flooding Attack")
    reset_database()
    
    # 1. Inisialisasi dengan 20% device jahat
    all_ids, malicious_ids = initialize_devices(total=15, malicious_ratio=0.2)
    normal_ids = list(set(all_ids) - malicious_ids)
    
    # 2. Fase Operasi Normal (2 Ronde)
    print("\n🔄 --- Phase 1: Normal Network Operation ---")
    for i in range(2):
        print(f"\n--- Normal Round {i+1} ---")
        for _ in range(15):
            rater, target = random.sample(normal_ids, 2)
            create_connection(rater, target, success=True)
            rate_peer(rater, target, calculate_smart_score(target, True))
            rate_peer(target, rater, calculate_smart_score(rater, True))
    
    
    # Hasil Akhir
    print("\n" + "="*50)
    print("📈 FINAL SYSTEM STATUS (after Flooding Attack)")
    print("="*50)
    devices = get_all_devices()
    for dev in sorted(devices, key=lambda x: x['id']):
        status = "🔴 MALICIOUS" if dev['id'] in malicious_ids else "🟢 NORMAL   "
        flagged = "🚩 FLAGGED" if dev['is_flagged'] else ""
        blacklisted = "☠️ BLACKLISTED" if dev['is_blacklisted'] else ""
        print(f"- {dev['id']} ({status}): {dev['trust_score']:.3f} | Suspicious: {dev['suspicious_count']:<2} {flagged} {blacklisted}")

    print("\n🏁 FLOODING SCENARIO COMPLETE")

if __name__ == "__main__":
    run_simulation()
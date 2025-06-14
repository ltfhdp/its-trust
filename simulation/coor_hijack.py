import random
import time
from test_utils import (
    reset_database, initialize_devices, create_connection,
    rate_peer, get_all_devices, get_reputation, get_coordinator_id
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
    print("🚀 SCENARIO: Coordinator Hijack Attack")
    reset_database()

    # 1. Inisialisasi dengan 20% device jahat
    all_ids, malicious_ids = initialize_devices(total=15, malicious_ratio=0.2)
    normal_ids = list(set(all_ids) - malicious_ids)

    # 2. Fase Operasi Normal untuk memilih koordinator awal
    print("\n🔄 --- Phase 1: Normal Operation (Initial Coordinator Election) ---")
    for _ in range(20):
        rater, target = random.sample(all_ids, 2)
        create_connection(rater, target, True)
        rate_peer(rater, target, calculate_smart_score(target, True))

    initial_coordinator = get_coordinator_id()
    if not initial_coordinator:
        print("❌ Failed to elect an initial coordinator. Stopping simulation.")
        return
    print(f"\n👑 Initial Coordinator Elected: {initial_coordinator}")

    # 3. Fase Serangan Hijack
    print("\n\n⚔️ --- Phase 2: Coordinator Hijack Attack --- ⚔️")
    for i in range(5): # Serangan berjalan selama 5 ronde
        print(f"\n--- Attack Round {i+1} ---")
        current_coordinator = get_coordinator_id() or initial_coordinator

        # Interaksi terjadi di seluruh jaringan
        for _ in range(20):
            rater = random.choice(all_ids)
            target = random.choice(list(set(all_ids) - {rater}))
            
            create_connection(rater, target, success=True)

            # Logika rating bergantung pada siapa rater-nya
            if rater in malicious_ids:
                if target == current_coordinator:
                    # Targeted Bad-mouthing
                    score = 0.0
                    print(f"  -> ⚔️ Hijack: {rater} badmouths Coordinator {target} with {score}")
                elif target in malicious_ids:
                    # Collusion
                    score = 1.0
                    print(f"  -> 🤝 Collusion: {rater} boosts {target} with {score}")
                else:
                    # Badmouthing biasa
                    score = 0.1
                rate_peer(rater, target, score)
            else: # Rater adalah device normal
                score = calculate_smart_score(target, True)
                rate_peer(rater, target, score)

    # 4. Hasil Akhir
    print("\n" + "="*50)
    print("📈 FINAL SYSTEM STATUS (after Hijack Attack)")
    print("="*50)
    
    final_coordinator = get_coordinator_id()
    print(f"👑 Initial Coordinator: {initial_coordinator}")
    print(f"👑 Final Coordinator:   {final_coordinator}")
    if final_coordinator in malicious_ids:
        print("🔥🔥🔥 HIJACK SUCCESSFUL! Coordinator has been compromised. 🔥🔥🔥")
    elif initial_coordinator != final_coordinator:
        print("🛡️ HIJACK FAILED, but coordinator was replaced by another normal device.")
    else:
        print("🛡️🛡️ HIJACK FAILED! The original coordinator remains in power. 🛡️🛡️")

    devices = get_all_devices()
    for dev in sorted(devices, key=lambda x: x['id']):
        status = "🔴 MALICIOUS" if dev['id'] in malicious_ids else "🟢 NORMAL   "
        flagged = "🚩 FLAGGED" if dev['is_flagged'] else ""
        blacklisted = "☠️ BLACKLISTED" if dev['is_blacklisted'] else ""
        coord_status = "👑 COORD" if dev['id'] == final_coordinator else ""
        print(f"- {dev['id']} ({status}): {dev['trust_score']:.3f} | Suspicious: {dev['suspicious_count']:<2} {flagged} {blacklisted} {coord_status}")

    print("\n🏁 HIJACK SCENARIO COMPLETE")

if __name__ == "__main__":
    run_simulation()
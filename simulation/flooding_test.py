import random
import time
from concurrent.futures import ThreadPoolExecutor
from test_utils import (
    reset_database, initialize_devices, create_connection,
    rate_peer, get_all_devices, get_reputation, register_device, leave_device
)

def calculate_smart_score(target_id: str, connection_success: bool) -> float:
    target_reputation = get_reputation(target_id)
    if not target_reputation or not target_reputation.get("exists"):
        return 0.5

    base_score = random.uniform(0.7, 1.0) if connection_success else random.uniform(0.1, 0.4)
    level = target_reputation.get("reputation_level", "AVERAGE")

    if level == "BLACKLISTED": return min(base_score, 0.1)
    if level == "VERY_SUSPICIOUS": return min(base_score, 0.15)
    if level == "SUSPICIOUS": return min(base_score, random.uniform(0.3, 0.5))
    if level == "POOR": return base_score * 0.9
    return round(max(0.0, min(1.0, base_score)), 2)

def flooding_parallel(attacker_id, normal_ids, count=30, max_workers=10):
    def one_connection():
        target = random.choice(normal_ids)
        print(f"  -> 🌊 Flooding: {attacker_id} → {target}")
        create_connection(attacker_id, target, True)  # langsung update trust
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(one_connection) for _ in range(count)]
        for f in futures:
            f.result()

def run_simulation():
    print("🚀 SCENARIO: Refactored Flooding Attack")
    reset_database()

    all_ids, malicious_ids = initialize_devices(total=15, malicious_ratio=0.2)
    normal_ids = list(set(all_ids) - malicious_ids)
    attacker_id = list(malicious_ids)[0]

    # Phase 1: Normal
    print("\n🔄 --- Phase 1: Normal Network Operation ---")
    for i in range(100):
        rater, target = random.sample(normal_ids, 2)
        create_connection(rater, target, True)
        rate_peer(rater, target, calculate_smart_score(target, True))
        rate_peer(target, rater, calculate_smart_score(rater, True))

    # Phase 2: Flooding
    print("\n🌊 --- Phase 2: Coordinated Flooding Attack ---")
    print(f"Observing attacker: {attacker_id}")
    for attacker_id in malicious_ids:
        flooding_parallel(attacker_id, normal_ids, count=30, max_workers=10)

    # Phase 3: Post-Attack Attempt
    print("\n🕊️ --- Phase 3: Post-Attack Check ---")
    target = normal_ids[0]
    print(f"  -> Test: {attacker_id} tries to connect to {target}")
    create_connection(attacker_id, target, True)

    # Phase 4: Rejoin Attempt
    print("\n🔬 --- Phase 4: Rejoin Test ---")
    print(f"  -> Device {attacker_id} attempts to leave and rejoin...")
    leave_device(attacker_id)
    time.sleep(1)
    register_device(attacker_id)

    # Final status
    print("\n📊 --- FINAL STATUS ---")
    devices = get_all_devices()
    for dev in sorted(devices, key=lambda x: x['id']):
        status = "🔴 MALICIOUS" if dev['id'] in malicious_ids else "🟢 NORMAL   "
        flagged = "🚩 FLAGGED" if dev['is_flagged'] else ""
        blacklisted = "☠️ BLACKLISTED" if dev['is_blacklisted'] else ""
        print(f"- {dev['id']} ({status}): {dev['trust_score']:.3f} | Suspicious: {dev['suspicious_count']} {flagged} {blacklisted}")

    print("\n🏁 SCENARIO COMPLETE")

if __name__ == "__main__":
    run_simulation()

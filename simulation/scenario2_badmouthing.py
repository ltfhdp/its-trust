import random
import time
from test_utils import (
    initialize_devices, create_connection,
    rate_peer, get_all_devices, get_reputation
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
    elif reputation_level == "POOR":
        adjusted_score = base_score * 0.9
    else: 
        adjusted_score = base_score
        
    return round(max(0.0, min(1.0, adjusted_score)), 2)


def run_simulation():
    print("SCENARIO 2: Badmouthing")
    
    all_ids, malicious_ids = initialize_devices()
    
    print("\n --- Simulating 100 interactions ---")
    
    for i in range(100):
        src = random.choice(all_ids)
        tgt = random.choice([i for i in all_ids if i != src])

        create_connection(src, tgt, success=True)
            
        # rating dari rater ke target
        if src in malicious_ids: 
            score_1 = round(random.uniform(0.1, 0.2), 2)
            print(f"  [🔴->⭐] {src} badmouths {tgt} with {score_1:.2f}")
        else:
            score_1 = calculate_smart_score(tgt, connection_success=True)
            print(f"  [🟢->⭐] {src} smart-rates {tgt} with {score_1:.2f}")
            
        rate_peer(src, tgt, score_1)

        # rating balasan dari target ke rater
        if tgt in malicious_ids:
            score_2 = round(random.uniform(0.1, 0.2), 2)
            print(f"  [..🔴] {tgt} badmouths {src} back with {score_2:.2f}")
        else:
            score_2 = calculate_smart_score(src, connection_success=True)
            print(f"  [..🟢] {tgt} smart-rates {src} back with {score_2:.2f}")

        rate_peer(tgt, src, score_2)

        print(f"  -> Iter {i+1}: {src} <-> {tgt} | Ratings: {score_1:.2f} / {score_2:.2f}")
            
        time.sleep(0.01)

    print("\n" + "="*50)
    print("FINAL TRUST SCORES")
    print("="*50)
    devices = get_all_devices()
    for dev in sorted(devices, key=lambda x: x['id']):
        status = "🔴 MALICIOUS" if dev['id'] in malicious_ids else "🟢 NORMAL   "
        blacklisted = " - BLACKLISTED" if dev['is_blacklisted'] else ""
        flagged = " - FLAGGED 🚩" if dev['is_flagged'] else ""
        print(f"- {dev['id']} ({status}): {dev['trust_score']:.3f}{blacklisted}{flagged}")

    print("\n SCENARIO 2 COMPLETE")


if __name__ == "__main__":
    run_simulation()
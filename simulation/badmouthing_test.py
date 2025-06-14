import random
import time
from test_utils import (
    reset_database, initialize_devices, create_connection,
    rate_peer, get_all_devices, get_reputation
)

def calculate_smart_score(target_id: str, connection_success: bool) -> float:
    """
    Memberikan rating cerdas berdasarkan info reputasi yang diambil dari API.
    Device normal akan menggunakan fungsi ini untuk menentukan skor.
    """
    target_reputation = get_reputation(target_id)
    
    if not target_reputation or not target_reputation.get("exists"):
        return 0.5  # Skor default jika device tidak ditemukan

    # Skor dasar berdasarkan hasil koneksi
    if connection_success:
        base_score = random.uniform(0.7, 1.0)
    else:
        base_score = random.uniform(0.1, 0.4)
        
    # Penyesuaian berdasarkan level reputasi dari backend
    reputation_level = target_reputation.get("reputation_level", "AVERAGE")
        
    if reputation_level == "BLACKLISTED":
        adjusted_score = min(base_score, 0.1)
    elif reputation_level == "VERY_SUSPICIOUS":
        adjusted_score = min(base_score, 0.15)
    elif reputation_level == "SUSPICIOUS":
        # Beri penalti sedang untuk yang sudah di-flag
        adjusted_score = min(base_score, random.uniform(0.3, 0.5))
    elif reputation_level == "POOR":
        adjusted_score = base_score * 0.9
    else: # GOOD, EXCELLENT, AVERAGE
        adjusted_score = base_score
        
    return round(max(0.0, min(1.0, adjusted_score)), 2)


def run_simulation():
    """
    Skenario Badmouthing:
    - Device Jahat: Selalu memberi skor rendah (tanpa kolusi).
    - Device Normal: Memberi skor menggunakan Smart Rating.
    """
    print("🚀 SCENARIO 2 (Hybrid): Badmouthing with Smart Rating (No Collusion)")
    reset_database()
    
    all_ids, malicious_ids = initialize_devices()
    
    print("\n🔄 --- Simulating 100 interactions ---")
    
    for i in range(100):
        rater = random.choice(all_ids)
        target = random.choice([i for i in all_ids if i != rater])

        create_connection(rater, target, success=True)
            
        # --- RATING 1: Dari Rater ke Target ---
        if rater in malicious_ids:
            # Device jahat selalu memberikan rating buruk (TIDAK ADA KOLUSI)
            score_1 = round(random.uniform(0.1, 0.2), 2)
            print(f"  [🔴->⭐] {rater} badmouths {target} with {score_1:.2f}")
        else:
            # Device normal menggunakan SMART RATING
            score_1 = calculate_smart_score(target, connection_success=True)
            print(f"  [🟢->⭐] {rater} smart-rates {target} with {score_1:.2f}")
            
        rate_peer(rater, target, score_1)

        # --- RATING 2: Rating Balasan dari Target ke Rater ---
        if target in malicious_ids:
            # Device jahat membalas dengan rating buruk
            score_2 = round(random.uniform(0.1, 0.2), 2)
            print(f"  [..🔴] {target} badmouths {rater} back with {score_2:.2f}")
        else:
            # Device normal membalas dengan SMART RATING
            score_2 = calculate_smart_score(rater, connection_success=True)
            print(f"  [..🟢] {target} smart-rates {rater} back with {score_2:.2f}")

        rate_peer(target, rater, score_2)
            
        time.sleep(0.01)

    # --- HASIL AKHIR ---
    print("\n" + "="*50)
    print("📈 FINAL TRUST SCORES")
    print("="*50)
    devices = get_all_devices()
    for dev in sorted(devices, key=lambda x: x['id']):
        status = "🔴 MALICIOUS" if dev['id'] in malicious_ids else "🟢 NORMAL   "
        blacklisted = " - BLACKLISTED ☠️" if dev['is_blacklisted'] else ""
        flagged = " - FLAGGED 🚩" if dev['is_flagged'] else ""
        print(f"- {dev['id']} ({status}): {dev['trust_score']:.3f}{blacklisted}{flagged}")

    print("\n🏁 SCENARIO 2 (Badmouthing Attack) COMPLETE")


if __name__ == "__main__":
    run_simulation()
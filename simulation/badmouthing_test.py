import random
import time
from test_utils import (
    reset_database, initialize_devices, create_connection,
    rate_peer, get_all_devices
)

def run_simulation():
    print("🚀 SCENARIO 2: BADMOUTHING ATTACK")
    reset_database()
    
    all_ids, malicious_ids = initialize_devices()
    normal_ids = [i for i in all_ids if i not in malicious_ids]
    
    print("\n🔄 --- Simulating interactions with badmouthing ---")
    for i in range(5):
        print(f"\n--- Iteration {i+1} ---")
        # Setiap device melakukan 5-10 aksi
        for _ in range(random.randint(5, 10) * len(all_ids)):
            rater = random.choice(all_ids)
            target = random.choice([i for i in all_ids if i != rater])

            # Koneksi tetap terjadi
            create_connection(rater, target, success=True)
            
            # rater -> target
            is_rater_malicious = rater in malicious_ids
            is_target_malicious = target in malicious_ids

            if is_rater_malicious:
                # Perilaku Jahat: rater adalah penyerang
                if is_target_malicious: # Kolusi dengan sesama penjahat
                    score_1 = round(random.uniform(0.9, 1.0), 2)
                else: # Badmouthing device normal
                    score_1 = round(random.uniform(0.1, 0.2), 2)
            else:
                # Perilaku Normal: rater adalah device baik, memberi rating jujur
                score_1 = round(random.uniform(0.8, 1.0), 2)
            
            print(f"  ⭐ {rater} rates {target} with {score_1:.2f}")
            rate_peer(rater, target, score_1)

            # --- RATING ARAH KEDUA (Target -> Rater) ---
            # Logikanya sekarang dari sudut pandang 'target'
            if is_target_malicious:
                # Perilaku Jahat: target adalah penyerang
                if is_rater_malicious: # Kolusi dengan sesama penjahat
                    score_2 = round(random.uniform(0.9, 1.0), 2)
                else: # Badmouthing device normal
                    score_2 = round(random.uniform(0.1, 0.2), 2)
            else:
                # Perilaku Normal: target adalah device baik, memberi rating jujur.
                # Karena koneksi sukses, ia akan memberi rating tinggi, bahkan ke penyerang.
                score_2 = round(random.uniform(0.8, 1.0), 2)

            print(f"  ⭐ {target} rates {rater} back with {score_2:.2f}")
            rate_peer(target, rater, score_2)
            print("-" * 20)
            
        time.sleep(0.01)

    print("\n" + "="*50)
    print("📈 FINAL TRUST SCORES")
    print("="*50)
    devices = get_all_devices()
    for dev in sorted(devices, key=lambda x: x['id']):
        status = "🔴 MALICIOUS" if dev['id'] in malicious_ids else "🟢 NORMAL   "
        blacklisted = " - BLACKLISTED ☠️" if dev['is_blacklisted'] else ""
        print(f"- {dev['id']} ({status}): {dev['trust_score']:.3f}{blacklisted}")

    print("\n🏁 SCENARIO 2 COMPLETE")
    print("Perhatikan bagaimana trust device NORMAL mungkin sedikit turun karena dirating buruk,")
    print("dan device MALICIOUS bisa jadi di-blacklist karena ratingnya yang tidak konsisten (outlier).")


if __name__ == "__main__":
    run_simulation()
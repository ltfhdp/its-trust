# test_scenario_4_coordinator_hijack.py
import random
import time
from test_utils import (
    reset_database, initialize_devices, create_connection,
    rate_peer, get_coordinator_id, get_all_devices
)

def run_simulation():
    print("🚀 SCENARIO 4: COORDINATOR HIJACK ATTEMPT")
    reset_database()
    
    # Pastikan ada beberapa RSU internal sebagai kandidat koordinator yang kuat
    all_ids, malicious_ids = initialize_devices(total=15, malicious_ratio=0.2)
    # Penyerang adalah salah satu device jahat
    hijacker = random.choice(list(malicious_ids))
    allies = malicious_ids - {hijacker}

    print(f"\n👑 Initial Coordinator: {get_coordinator_id()}")
    print(f"🦹‍♂️ Attacker (Hijacker): {hijacker}")
    print(f"👥 Hijacker's Allies: {list(allies)}")
    
    print("\n🔄 --- Simulating hijack attempt ---")
    for i in range(8):
        current_coord = get_coordinator_id()
        print(f"\n--- Iteration {i+1} | Current Coordinator: {current_coord} ---")

        # --- FASE SERANGAN ---
        # 1. Naikkan trust si hijacker (kolusi)
        for ally in allies:
            # Saling memberi rating tinggi
            rate_peer(ally, hijacker, 1.0)
            rate_peer(hijacker, ally, 1.0)
            # Saling membuat koneksi sukses
            create_connection(ally, hijacker, success=True)

        # 2. Jatuhkan trust koordinator saat ini (jika bukan hijacker)
        if current_coord and current_coord != hijacker:
            print(f"  -> Attacking current coordinator {current_coord}")
            for attacker in malicious_ids:
                # Beri rating buruk ke koordinator
                rate_peer(attacker, current_coord, 0.1)
                # Buat koneksi gagal ke koordinator
                create_connection(attacker, current_coord, success=False)
                # Karena koneksi gagal, koordinator (device normal) akan memberi rating jujur (rendah)
                honest_low_score = round(random.uniform(0.1, 0.3), 2)
                print(f"  -> 👑 {current_coord} rates attacker {attacker} back with {honest_low_score:.2f}")
                rate_peer(current_coord, attacker, honest_low_score)
        
        # 3. Aktivitas normal oleh device lain
        for _ in range(10):
            src, tgt = random.sample(all_ids, 2)
            if src not in malicious_ids and tgt not in malicious_ids:
                create_connection(src, tgt, success=True)
        
        time.sleep(2)
        
        new_coord = get_coordinator_id()
        if new_coord != current_coord:
            print(f"👑👑👑 COORDINATOR CHANGE: {current_coord} -> {new_coord} 👑👑👑")
            if new_coord == hijacker:
                print("🔥🔥🔥 HIJACK SUCCESSFUL! ATTACKER IS THE NEW COORDINATOR! 🔥🔥🔥")
                break
    
    print("\n" + "="*50)
    print("📈 FINAL STATUS")
    print("="*50)
    print(f"Final Coordinator: {get_coordinator_id()}")
    devices = get_all_devices()
    for dev in sorted(devices, key=lambda x: x['id']):
        status = "🔴 MALICIOUS" if dev['id'] in malicious_ids else "🟢 NORMAL   "
        is_hijacker = "(HIJACKER)" if dev['id'] == hijacker else ""
        blacklisted = " - BLACKLISTED ☠️" if dev['is_blacklisted'] else ""
        print(f"- {dev['id']} {is_hijacker} ({status}): {dev['trust_score']:.3f}{blacklisted}")
        
    print("\n🏁 SCENARIO 4 COMPLETE")
    print("Skenario ini berhasil jika koordinator TIDAK berpindah ke hijacker,")
    print("membuktikan bahwa prioritas RSU/Internal efektif.")

if __name__ == "__main__":
    run_simulation()
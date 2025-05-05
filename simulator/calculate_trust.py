import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.trust import (
    calculate_initial_trust, get_computing_weight, get_memory_weight,
    calculate_updated_trust, get_connection_status_score
)

devices = [
    {"id": "rsu-1", "name": "RSU Utama", "ownership_type": "internal", "device_type": "RSU", "memory_gb": 16, "location": "Jalan Utama"},
    {"id": "sensor-1", "name": "Sensor Kecepatan 1", "ownership_type": "external", "device_type": "Sensor", "memory_gb": 2, "location": "Gerbang Barat"},
    {"id": "sensor-2", "name": "Sensor Suhu", "ownership_type": "external", "device_type": "Sensor", "memory_gb": 1, "location": "Pintu Timur"},
    {"id": "cam-1", "name": "Kamera CCTV A", "ownership_type": "external", "device_type": "Smart Device", "memory_gb": 4, "location": "Pasar Minggu"},
    {"id": "phone-1", "name": "User Smartphone", "ownership_type": "external", "device_type": "Smartphone", "memory_gb": 6, "location": "Dekat RS"}
]


print("INITIAL TRUST CALCULATION")
for device in devices:
    initial_trust = calculate_initial_trust(device["ownership_type"], device["memory_gb"])
    computing_power = get_computing_weight(device["device_type"])
    memory_weight = get_memory_weight(device["memory_gb"])
    
    print(f"Device: {device['id']} ({device['name']}-{device['ownership_type']})")
    print(f"  Type: {device['device_type']}, Memory: {device['memory_gb']} GB")
    print(f"  Computing Weight: {computing_power}, Memory Weight: {memory_weight}")
    print(f"  Initial Trust Score: {initial_trust}")
    print("-" * 50)

# simulasi update trust update setelah koneksi
def simulate_connection(device1, device2, success=True):
    # default values buat simulasi sederhana cek kalkulasi
    centrality_score = 0.2  
    avg_peer_rating = 0.5  
    conn_score = get_connection_status_score(success)
    
    # menghitung update trust device1
    initial_trust = calculate_initial_trust(device1["ownership_type"], device1["memory_gb"])
    updated_trust = calculate_updated_trust(
        last_trust=initial_trust,
        centrality_score=centrality_score,
        avg_peer_rating=avg_peer_rating,
        connection_status_score=conn_score
    )
    
    print(f"\nSimulated Connection: {device1['id']} → {device2['id']} ({'Success' if success else 'Failed'})")
    print(f"  {device1['id']} Trust before: {initial_trust}")
    print(f"  {device1['id']} Trust after: {updated_trust}")
    print(f"  Change: {updated_trust - initial_trust:+.3f}")
    
    # Print the calculation components
    print("\nCalculation Details:")
    print(f"  Last Trust: {initial_trust} × 0.5 = {initial_trust * 0.5}")
    print(f"  Centrality: {centrality_score} × 0.1 = {centrality_score * 0.1}")
    print(f"  Peer Rating: {avg_peer_rating} × 0.2 = {avg_peer_rating * 0.2}")
    print(f"  Connection: {conn_score} × 0.2 = {conn_score * 0.2}")
    print(f"  Total: {initial_trust * 0.5} + {centrality_score * 0.1} + {avg_peer_rating * 0.2} + {conn_score * 0.2} = {updated_trust}")

print("\nCONNECTION SIMULATION")
# Run example simulations
simulate_connection(devices[0], devices[3])  # rsu-1 ke cam-1 (success)
simulate_connection(devices[0], devices[3], False)  # rsu-1 ke cam-1 (failure)
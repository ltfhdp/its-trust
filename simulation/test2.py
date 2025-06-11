import requests
import random
import time
import uuid
from enum import Enum
from typing import Dict, List, Tuple
from dataclasses import dataclass

BASE_URL = "http://localhost:8000"

# Konfigurasi simulasi
TOTAL_DEVICES = 20
RSU_COUNT = 3  # RSU selalu internal
COMPUTER_COUNT = 4  # Mix internal/external
SMARTPHONE_COUNT = 8  # Mayoritas external
SMART_DEVICE_COUNT = 3  # Mix
SENSOR_COUNT = 2  # Mayoritas external

MALICIOUS_PERCENT = 0.15  # 15% malicious devices
SIMULATION_ROUNDS = 1
TRANSACTIONS_PER_ROUND = 40

class DeviceType(Enum):
    RSU = "RSU"
    COMPUTER = "Computer" 
    SMARTPHONE = "Smartphone"
    SMART_DEVICE = "Smart Device"
    SENSOR = "Sensor"

class ActivityType(Enum):
    # RSU Activities
    BROADCAST_TRAFFIC_INFO = "broadcast_traffic_info"
    PROPAGATE_TRUST_DATA = "propagate_trust_data"
    COORDINATE_NETWORK = "coordinate_network"
    
    # Vehicle/Smartphone Activities  
    REQUEST_TRAFFIC_DATA = "request_traffic_data"
    SHARE_LOCATION_DATA = "share_location_data"
    REQUEST_ROUTE_INFO = "request_route_info"
    
    # Smart Device Activities
    SEND_SENSOR_DATA = "send_sensor_data"
    REQUEST_CONFIG_UPDATE = "request_config_update"
    
    # General Activities
    PEER_DISCOVERY = "peer_discovery"
    DATA_SYNC = "data_sync"
    TRUST_VERIFICATION = "trust_verification"

@dataclass
class Device:
    id: str
    name: str
    device_type: DeviceType
    ownership_type: str
    memory_gb: int
    location: str
    is_malicious: bool = False

class IoTSimulator:
    def __init__(self):
        self.devices: List[Device] = []
        self.malicious_devices: set = set()
        self.coordinator_id: str = None
        
        # Activity patterns berdasarkan device type
        self.activity_patterns = {
            DeviceType.RSU: [
                ActivityType.BROADCAST_TRAFFIC_INFO,
                ActivityType.PROPAGATE_TRUST_DATA, 
                ActivityType.COORDINATE_NETWORK,
                ActivityType.TRUST_VERIFICATION
            ],
            DeviceType.COMPUTER: [
                ActivityType.REQUEST_TRAFFIC_DATA,
                ActivityType.DATA_SYNC,
                ActivityType.TRUST_VERIFICATION,
                ActivityType.PEER_DISCOVERY
            ],
            DeviceType.SMARTPHONE: [
                ActivityType.SHARE_LOCATION_DATA,
                ActivityType.REQUEST_ROUTE_INFO,
                ActivityType.REQUEST_TRAFFIC_DATA,
                ActivityType.PEER_DISCOVERY
            ],
            DeviceType.SMART_DEVICE: [
                ActivityType.SEND_SENSOR_DATA,
                ActivityType.REQUEST_CONFIG_UPDATE,
                ActivityType.DATA_SYNC
            ],
            DeviceType.SENSOR: [
                ActivityType.SEND_SENSOR_DATA,
                ActivityType.REQUEST_CONFIG_UPDATE
            ]
        }
        
        # Connection probability berdasarkan device type combination
        self.connection_probabilities = {
            (DeviceType.RSU, DeviceType.RSU): 0.9,  # RSU saling koordinasi
            (DeviceType.RSU, DeviceType.COMPUTER): 0.8,
            (DeviceType.RSU, DeviceType.SMARTPHONE): 0.7,
            (DeviceType.RSU, DeviceType.SMART_DEVICE): 0.6,
            (DeviceType.RSU, DeviceType.SENSOR): 0.5,
            
            (DeviceType.COMPUTER, DeviceType.COMPUTER): 0.6,
            (DeviceType.COMPUTER, DeviceType.SMARTPHONE): 0.7,
            (DeviceType.COMPUTER, DeviceType.SMART_DEVICE): 0.5,
            (DeviceType.COMPUTER, DeviceType.SENSOR): 0.4,
            
            (DeviceType.SMARTPHONE, DeviceType.SMARTPHONE): 0.5,
            (DeviceType.SMARTPHONE, DeviceType.SMART_DEVICE): 0.4,
            (DeviceType.SMARTPHONE, DeviceType.SENSOR): 0.3,
            
            (DeviceType.SMART_DEVICE, DeviceType.SMART_DEVICE): 0.4,
            (DeviceType.SMART_DEVICE, DeviceType.SENSOR): 0.6,
            
            (DeviceType.SENSOR, DeviceType.SENSOR): 0.3
        }

    def generate_devices(self):
        """Generate devices dengan distribusi realistis"""
        device_configs = [
            # RSU - selalu internal, high memory
            *[(DeviceType.RSU, "internal", random.randint(8, 16)) for _ in range(RSU_COUNT)],
            
            # Computer - mix internal/external  
            *[(DeviceType.COMPUTER, random.choice(["internal", "external"]), random.randint(4, 16)) 
              for _ in range(COMPUTER_COUNT)],
            
            # Smartphone - mayoritas external
            *[(DeviceType.SMARTPHONE, "external" if random.random() < 0.8 else "internal", 
               random.randint(2, 8)) for _ in range(SMARTPHONE_COUNT)],
            
            # Smart Device - mix
            *[(DeviceType.SMART_DEVICE, random.choice(["internal", "external"]), 
               random.randint(1, 4)) for _ in range(SMART_DEVICE_COUNT)],
            
            # Sensor - mayoritas external, low memory
            *[(DeviceType.SENSOR, "external" if random.random() < 0.9 else "internal", 
               random.randint(1, 2)) for _ in range(SENSOR_COUNT)]
        ]
        
        locations = ["Zone_A", "Zone_B", "Zone_C", "Zone_D"]
        
        for i, (dev_type, ownership, memory) in enumerate(device_configs):
            device_id = f"{dev_type.value.lower().replace(' ', '_')}-{i:03}"
            
            device = Device(
                id=device_id,
                name=f"{dev_type.value} {i:03}",
                device_type=dev_type,
                ownership_type=ownership,
                memory_gb=memory,
                location=random.choice(locations)
            )
            
            self.devices.append(device)
        
        # Pilih malicious devices (hindari RSU internal)
        non_critical_devices = [d for d in self.devices 
                               if not (d.device_type == DeviceType.RSU and d.ownership_type == "internal")]
        
        malicious_count = int(len(self.devices) * MALICIOUS_PERCENT)
        malicious_selection = random.sample(non_critical_devices, malicious_count)
        
        for device in malicious_selection:
            device.is_malicious = True
            self.malicious_devices.add(device.id)
        
        print(f"🏗️  Generated {len(self.devices)} devices:")
        print(f"   RSU: {RSU_COUNT} (all internal)")
        print(f"   Computer: {COMPUTER_COUNT}")
        print(f"   Smartphone: {SMARTPHONE_COUNT}")
        print(f"   Smart Device: {SMART_DEVICE_COUNT}")
        print(f"   Sensor: {SENSOR_COUNT}")
        print(f"   Malicious: {len(malicious_selection)} devices")

    def register_device(self, device: Device):
        """Register device ke system"""
        payload = {
            "id": device.id,
            "name": device.name,
            "ownership_type": device.ownership_type,
            "device_type": device.device_type.value,
            "memory_gb": device.memory_gb,
            "location": device.location,
        }
        
        try:
            res = requests.post(f"{BASE_URL}/device", json=payload)
            status = "✅" if res.status_code == 200 else "❌"
            print(f"{status} Register {device.id} ({device.device_type.value}, {device.ownership_type})")
            return res.status_code == 200
        except Exception as e:
            print(f"❌ Error registering {device.id}: {e}")
            return False

    def get_connection_probability(self, src_device: Device, tgt_device: Device) -> float:
        """Hitung probabilitas koneksi berdasarkan device types"""
        src_type, tgt_type = src_device.device_type, tgt_device.device_type
        
        # Cek both directions
        prob = self.connection_probabilities.get((src_type, tgt_type))
        if prob is None:
            prob = self.connection_probabilities.get((tgt_type, src_type), 0.3)
        
        # Boost probability if coordinator involved
        if self.coordinator_id and (src_device.id == self.coordinator_id or tgt_device.id == self.coordinator_id):
            prob = min(1.0, prob + 0.2)
        
        # Reduce probability for malicious devices (others might avoid them)
        if src_device.is_malicious or tgt_device.is_malicious:
            prob *= 0.7
            
        return prob

    def select_target_device(self, src_device: Device, activity: ActivityType) -> Device:
        """Pilih target device berdasarkan activity type"""
        candidates = [d for d in self.devices if d.id != src_device.id]
        
        # Filter candidates berdasarkan activity
        if activity in [ActivityType.BROADCAST_TRAFFIC_INFO, ActivityType.PROPAGATE_TRUST_DATA]:
            # RSU broadcast ke semua tipe
            pass
        elif activity == ActivityType.COORDINATE_NETWORK:
            # RSU koordinasi dengan RSU lain atau high-end devices
            candidates = [d for d in candidates if d.device_type in [DeviceType.RSU, DeviceType.COMPUTER]]
        elif activity == ActivityType.REQUEST_TRAFFIC_DATA:
            # Request ke RSU atau Computer
            candidates = [d for d in candidates if d.device_type in [DeviceType.RSU, DeviceType.COMPUTER]]
        elif activity == ActivityType.SEND_SENSOR_DATA:
            # Sensor kirim ke RSU atau Smart Device
            candidates = [d for d in candidates if d.device_type in [DeviceType.RSU, DeviceType.SMART_DEVICE]]
        
        if not candidates:
            candidates = [d for d in self.devices if d.id != src_device.id]
        
        # Weighted selection berdasarkan connection probability
        weights = [self.get_connection_probability(src_device, d) for d in candidates]
        
        if sum(weights) == 0:
            return random.choice(candidates)
        
        return random.choices(candidates, weights=weights)[0]

    def simulate_connection(self, src_device: Device, tgt_device: Device, activity: ActivityType):
        """Simulasi koneksi dengan behavior realistis"""
        
        # Tentukan success rate berdasarkan factors
        base_success_rate = 0.85
        
        # Malicious devices sering gagal
        if src_device.is_malicious:
            if activity in [ActivityType.BROADCAST_TRAFFIC_INFO, ActivityType.COORDINATE_NETWORK]:
                # Malicious flooding attack
                success_rate = 0.1  # Mostly fail
            else:
                success_rate = 0.3
        else:
            success_rate = base_success_rate
            
            # Connection probability affects success
            conn_prob = self.get_connection_probability(src_device, tgt_device)
            success_rate = min(success_rate, conn_prob + 0.1)
        
        # Determine success
        is_success = random.random() < success_rate
        
        # Record connection
        self.record_connection(src_device.id, tgt_device.id, is_success, activity.value)
        
        # Peer rating berdasarkan hasil koneksi
        self.handle_peer_rating(src_device, tgt_device, is_success)
        
        return is_success

    def record_connection(self, src_id: str, tgt_id: str, status: bool, connection_type: str):
        """Record connection ke backend"""
        payload = {
            "device_id": src_id,
            "connected_device_id": tgt_id,
            "status": status,
            "connection_type": connection_type
        }
        
        try:
            res = requests.post(f"{BASE_URL}/connect", json=payload)
            status_icon = "✅" if status else "❌"
            print(f"   {status_icon} {src_id} → {tgt_id} ({connection_type})")
        except Exception as e:
            print(f"   ❌ Connection error: {e}")

    def handle_peer_rating(self, src_device: Device, tgt_device: Device, connection_success: bool):
        """Handle peer rating berdasarkan hasil koneksi"""
        
        # Probabilitas memberikan rating
        rating_probability = 0.4  # 40% chance to rate
        if not random.random() < rating_probability:
            return
        
        # Tentukan rating berdasarkan success dan device behavior
        if connection_success:
            if src_device.is_malicious:
                # Malicious device: bad-mouthing attack
                if random.random() < 0.7:  # 70% chance malicious rating
                    rating = random.uniform(0.0, 0.3)  # Bad rating
                else:
                    rating = random.uniform(0.8, 1.0)  # Occasional good rating (outlier)
            else:
                # Normal device: good rating for successful connection
                rating = random.uniform(0.8, 1.0)
        else:
            if src_device.is_malicious:
                # Malicious device: inconsistent rating
                rating = random.uniform(0.0, 0.4)
            else:
                # Normal device: bad rating for failed connection
                rating = random.uniform(0.0, 0.3)
        
        # Submit rating dengan probabilitas
        self.submit_peer_rating(src_device.id, tgt_device.id, rating, 
                               f"Connection {'success' if connection_success else 'failed'}")

    def submit_peer_rating(self, rater_id: str, rated_id: str, score: float, comment: str):
        """Submit peer rating"""
        payload = {
            "rater_device_id": rater_id,
            "rated_device_id": rated_id,
            "score": round(score, 2),
            "comment": comment,
            "update_trust": False  # Let normal trust update handle it
        }
        
        try:
            res = requests.post(f"{BASE_URL}/rate_peer/", json=payload)
            print(f"   📊 {rater_id} rated {rated_id}: {score:.2f}")
        except Exception as e:
            print(f"   ❌ Rating error: {e}")

    def get_coordinator(self):
        """Get current coordinator"""
        try:
            res = requests.get(f"{BASE_URL}/coordinator")
            if res.status_code == 200:
                coord_data = res.json()
                self.coordinator_id = coord_data['id']
                return coord_data
        except:
            pass
        return None

    def run_simulation_round(self, round_num: int):
        """Jalankan satu round simulasi"""
        print(f"\n🎯 === ROUND {round_num} ===")
        
        # Update coordinator info
        coordinator = self.get_coordinator()
        if coordinator:
            print(f"👑 Coordinator: {coordinator['id']} (Trust: {coordinator['trust_score']:.3f})")
        
        for transaction in range(TRANSACTIONS_PER_ROUND):
            # Pilih source device
            src_device = random.choice(self.devices)
            
            # Pilih activity berdasarkan device type
            possible_activities = self.activity_patterns[src_device.device_type]
            activity = random.choice(possible_activities)
            
            # Pilih target device
            tgt_device = self.select_target_device(src_device, activity)
            
            # Simulasi koneksi
            print(f"🔄 Transaction {transaction+1}: {src_device.id} → {activity.value}")
            self.simulate_connection(src_device, tgt_device, activity)
            
            # Small delay
            time.sleep(0.05)
        
        print(f"✅ Round {round_num} completed")

    def print_final_stats(self):
        """Print statistik akhir"""
        try:
            res = requests.get(f"{BASE_URL}/devices/")
            if res.status_code == 200:
                devices = res.json()
                
                print(f"\n📊 === FINAL STATISTICS ===")
                print(f"{'Device ID':<15} {'Type':<12} {'Trust':<6} {'Connections':<11} {'Status':<10}")
                print("-" * 65)
                
                for device in devices:
                    status = "BLACKLIST" if device['is_blacklisted'] else "ACTIVE"
                    if device['is_coordinator']:
                        status = "COORDINATOR"
                    
                    malicious_mark = "🚨" if device['id'] in self.malicious_devices else ""
                    
                    print(f"{device['id']:<15} {device['device_type']:<12} "
                          f"{device['trust_score']:<6.3f} {device['connection_count']:<11} "
                          f"{status:<10} {malicious_mark}")
                
                # Summary
                active_devices = [d for d in devices if not d['is_blacklisted']]
                blacklisted = [d for d in devices if d['is_blacklisted']]
                
                print(f"\n📈 Summary:")
                print(f"   Total Devices: {len(devices)}")
                print(f"   Active: {len(active_devices)}")
                print(f"   Blacklisted: {len(blacklisted)}")
                print(f"   Malicious Detected: {sum(1 for d in blacklisted if d['id'] in self.malicious_devices)}")
                
        except Exception as e:
            print(f"Error getting final stats: {e}")

    def run_full_simulation(self):
        """Jalankan simulasi lengkap"""
        #print("🚀 Starting Enhanced IoT Trust System Simulation")
        #print("=" * 50)
        
        # Generate dan register devices
        self.generate_devices()
        
        print(f"\n📡 Registering devices...")
        for device in self.devices:
            self.register_device(device)
            time.sleep(0.02)  # Small delay
        
        # Run simulation rounds
        for round_num in range(1, SIMULATION_ROUNDS + 1):
            self.run_simulation_round(round_num)
            time.sleep(0.5)  # Delay between rounds
        
        # Print final statistics
        self.print_final_stats()
        
        print(f"\n🏁 Simulation completed!")

if __name__ == "__main__":
    simulator = IoTSimulator()
    simulator.run_full_simulation()
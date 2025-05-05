import requests
import time
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from tabulate import tabulate

# Set the API base URL
API_BASE = "http://localhost:8000"

def create_connection(source_id, target_id, status=True):
    """Create a connection between two devices"""
    res = requests.post(f"{API_BASE}/connect/", json={
        "device_id": source_id,
        "connected_device_id": target_id,
        "status": status
    })
    if res.status_code == 200:
        print(f"{source_id} → {target_id}: {'✔' if status else '✘'}")
        return status
    else:
        print(f"Failed to create connection: {res.status_code}")
        return None

def get_all_devices():
    """Get information about all devices"""
    res = requests.get(f"{API_BASE}/devices/")
    if res.status_code == 200:
        return res.json()
    else:
        print(f"Failed to get devices: {res.status_code}")
        return []

def get_device_history(device_id):
    """Get trust history for a specific device"""
    res = requests.get(f"{API_BASE}/device/{device_id}/history")
    if res.status_code == 200:
        return res.json()
    else:
        print(f"Failed to get history for {device_id}: {res.status_code}")
        return []

def display_device_table():
    """Display a table of all devices and their trust scores"""
    devices = get_all_devices()
    if not devices:
        return
    
    data = []
    for d in devices:
        data.append([
            d["id"], 
            d["name"],
            f"{d['trust_score']:.3f}",
            d["successful_connections"],
            d["failed_connections"],
            d["is_blacklisted"],
            d["is_coordinator"]
        ])
    
    headers = ["ID", "Name", "Trust", "Success", "Fails", "Blacklisted", "Coordinator"]
    print("\nDevice Status:")
    print(tabulate(data, headers=headers, tablefmt="grid"))

def demonstrate_interaction_details():
    """Demonstrate interactions and show rating/centrality details using registered devices"""

    print("\n=== DEMONSTRATING INTERACTION DETAILS (Using Registered Devices) ===")

    # Fetch all devices from the database
    all_devices = get_all_devices()
    if not all_devices or len(all_devices) < 3:
        print("Error: Not enough devices registered in the database.")
        return

    device1 = all_devices[0]["id"]
    device2 = all_devices[1]["id"]
    device3 = all_devices[2]["id"]

    print(f"\n--- Scenario: {device1} interacts with {device2} and {device3} ---")

    # Simulate connections
    status_1_to_2 = create_connection(device1, device2, True)
    status_1_to_3 = create_connection(device1, device3, False)
    status_2_to_1 = create_connection(device2, device1, True)
    status_3_to_1 = create_connection(device3, device1, False)

    if status_1_to_2 is not None and status_1_to_3 is not None and status_2_to_1 is not None and status_3_to_1 is not None:
        # Display Ratings
        print("\n--- Ratings ---")
        print(f"{device1} rated {device2}: {'1.0' if status_1_to_2 else '0.0'}")
        print(f"{device1} rated {device3}: {'1.0' if status_1_to_3 else '0.0'}")
        print(f"{device2} rated {device1}: {'1.0' if status_2_to_1 else '0.0'}")
        print(f"{device3} rated {device1}: {'1.0' if status_3_to_1 else '0.0'}")

        # Display Connections for Centrality
        print("\n--- Connections for Centrality ---")
        all_devices = get_all_devices()
        for device in all_devices:
            connected_devices = []
            for conn in device["connections_received"]:
                connected_devices.append(conn["source_device_id"])
            unique_connected_devices = list(set(connected_devices))
            print(f"{device['id']} is connected to: {unique_connected_devices} (Total: {len(unique_connected_devices)})")

    display_device_table()

def simulate_trust_dynamics():
    """Run a complete simulation demonstrating trust dynamics with registered devices"""
    display_device_table()
    
    # Demonstrate interaction details
    demonstrate_interaction_details()
    
    
    print("\nSimulation complete!")

if __name__ == "__main__":
    simulate_trust_dynamics()
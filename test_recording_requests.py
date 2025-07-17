#!/usr/bin/env python3
"""
Test script to verify recording request functionality
"""

import requests
import json
import os 
from dotenv import load_dotenv
load_dotenv()


# Base URL for the Django server
BASE_URL = os.environ.get("base_url",None) # Change this to your server's URL if needed

def test_recording_requests():
    """Test the recording request functionality"""
    
    print("=== Testing Recording Request System ===\n")
    
    # First, let's test if the server is accessible
    print("0. Testing server accessibility...")
    try:
        response = requests.get(f"{BASE_URL}/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print("   Server is accessible")
        else:
            print(f"   Server returned: {response.status_code}")
    except Exception as e:
        print(f"   Exception: {e}")
        return
    
    # Test 1: Get recording requests for room 12 (should have requests)
    print("\n1. Testing get_recording_requests for room 12...")
    try:
        response = requests.get(f"{BASE_URL}/api/get-recording-requests/12/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
        elif response.status_code == 302:
            print("   Redirected (likely to login page)")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    print("\n2. Testing get_recording_requests for room 'Namo'...")
    try:
        # First get the room ID for 'Namo'
        response = requests.get(f"{BASE_URL}/api/get-recording-requests/2/")  # Assuming room ID 2
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
        elif response.status_code == 302:
            print("   Redirected (likely to login page)")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    print("\n3. Testing get_available_approvers for room 12...")
    try:
        response = requests.get(f"{BASE_URL}/api/get-available-approvers/12/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
        elif response.status_code == 302:
            print("   Redirected (likely to login page)")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    print("\n4. Testing has_recording_permission for room 12...")
    try:
        response = requests.get(f"{BASE_URL}/api/has-recording-permission/12/")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")
        elif response.status_code == 302:
            print("   Redirected (likely to login page)")
        else:
            print(f"   Error: {response.text}")
    except Exception as e:
        print(f"   Exception: {e}")

if __name__ == "__main__":
    test_recording_requests() 
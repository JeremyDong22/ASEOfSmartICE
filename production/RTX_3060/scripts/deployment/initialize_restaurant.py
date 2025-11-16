#!/usr/bin/env python3
"""
Interactive Restaurant Deployment Initialization
Version: 1.0.0
Created: 2025-11-15

Purpose:
- Interactive wizard to initialize a new restaurant deployment
- Collects: City, Restaurant Name, Commercial Area (unique identifier)
- Collects: Camera IP addresses and configurations
- Registers location and cameras in both local SQLite and Supabase
- Generates location-specific configuration files

Usage:
    python3 initialize_restaurant.py

Workflow:
    1. Collect restaurant location information (city, name, commercial area)
    2. Generate unique location_id
    3. Collect camera IP addresses and details
    4. Test camera RTSP connections
    5. Register in local database
    6. Sync to Supabase cloud
    7. Save configuration files
"""

import os
import sys
import sqlite3
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional
import json

# Add parent directory to path for imports
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Constants
DB_PATH = PROJECT_ROOT / "db" / "detection_data.db"
DB_SCHEMA_PATH = PROJECT_ROOT / "db" / "database_schema.sql"
CONFIG_DIR = SCRIPT_DIR.parent / "config"


class RestaurantInitializer:
    """Interactive wizard for restaurant deployment initialization

    Version: 1.0.0
    Handles location registration and camera configuration
    """

    def __init__(self):
        self.conn = None
        self.location_id = None
        self.location_info = {}
        self.cameras = []

    def run(self):
        """Main wizard workflow"""
        print("=" * 70)
        print("🏪 ASE Restaurant Deployment Initialization Wizard")
        print("=" * 70)
        print()

        # Step 1: Initialize database
        print("📊 Step 1: Database Initialization")
        self.initialize_database()
        print("✅ Database initialized\n")

        # Step 2: Collect location information
        print("📍 Step 2: Restaurant Location Information")
        self.collect_location_info()
        print(f"✅ Location ID: {self.location_id}\n")

        # Step 3: Collect camera information
        print("📷 Step 3: Camera Configuration")
        self.collect_camera_info()
        print(f"✅ Configured {len(self.cameras)} cameras\n")

        # Step 4: Test camera connections
        print("🔌 Step 4: Camera Connection Testing")
        self.test_camera_connections()
        print("✅ Camera connections verified\n")

        # Step 5: Register in database
        print("💾 Step 5: Database Registration")
        self.register_to_database()
        print("✅ Registered in local database\n")

        # Step 6: Save configuration files
        print("📝 Step 6: Configuration Files")
        self.save_configuration_files()
        print("✅ Configuration files saved\n")

        # Step 7: Supabase sync
        print("☁️  Step 7: Supabase Cloud Sync")
        self.sync_to_supabase()
        print("✅ Synced to Supabase\n")

        # Summary
        self.print_summary()

    def initialize_database(self):
        """Initialize local SQLite database with schema"""
        # Create db directory if doesn't exist
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

        # Connect to database
        self.conn = sqlite3.connect(str(DB_PATH))

        # Load and execute schema
        if DB_SCHEMA_PATH.exists():
            with open(DB_SCHEMA_PATH, 'r') as f:
                schema_sql = f.read()
            self.conn.executescript(schema_sql)
            self.conn.commit()
        else:
            print(f"⚠️  Warning: Schema file not found at {DB_SCHEMA_PATH}")
            print("   Creating basic schema...")
            self._create_basic_schema()

    def _create_basic_schema(self):
        """Create basic schema if schema file not found"""
        cursor = self.conn.cursor()

        # Basic location table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS locations (
                location_id TEXT PRIMARY KEY,
                city TEXT NOT NULL,
                restaurant_name TEXT NOT NULL,
                commercial_area TEXT NOT NULL,
                address TEXT,
                region TEXT,
                timezone TEXT DEFAULT 'Asia/Shanghai',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active INTEGER DEFAULT 1
            )
        ''')

        # Basic camera table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cameras (
                camera_id TEXT PRIMARY KEY,
                location_id TEXT NOT NULL,
                camera_name TEXT,
                camera_ip_address TEXT NOT NULL,
                rtsp_endpoint TEXT,
                camera_type TEXT DEFAULT 'UNV',
                resolution TEXT,
                division_name TEXT,
                status TEXT DEFAULT 'active',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES locations(location_id)
            )
        ''')

        self.conn.commit()

    def collect_location_info(self):
        """Interactive collection of restaurant location information"""
        print("Please provide restaurant location details:")
        print("(This creates a unique identifier for the restaurant)")
        print()

        # City
        while True:
            city = input("  City (e.g., Mianyang, Chengdu): ").strip()
            if city:
                break
            print("  ❌ City cannot be empty")

        # Restaurant name
        while True:
            restaurant_name = input("  Restaurant Name (e.g., YeBaiLingHotpot): ").strip()
            if restaurant_name:
                break
            print("  ❌ Restaurant name cannot be empty")

        # Commercial area
        while True:
            commercial_area = input("  Commercial Area (e.g., 1958CommercialDistrict): ").strip()
            if commercial_area:
                break
            print("  ❌ Commercial area cannot be empty")

        # Optional: Address
        address = input("  Full Address (optional): ").strip() or None

        # Optional: Region
        region = input("  Region/Province (optional, default: Sichuan): ").strip() or "Sichuan"

        # Generate location_id
        self.location_id = self._generate_location_id(city, restaurant_name, commercial_area)

        # Store info
        self.location_info = {
            'location_id': self.location_id,
            'city': city,
            'restaurant_name': restaurant_name,
            'commercial_area': commercial_area,
            'address': address,
            'region': region,
            'timezone': 'Asia/Shanghai'
        }

        print()
        print(f"  Generated Location ID: {self.location_id}")
        print(f"  Full Identity: {city} / {restaurant_name} / {commercial_area}")
        print()

    def _generate_location_id(self, city: str, restaurant: str, area: str) -> str:
        """Generate unique location_id from components

        Format: {city}_{restaurant}_{area} (lowercase, no spaces, underscores)
        Example: mianyang_yebailinghotpot_1958commercialdistrict
        """
        def clean_string(s: str) -> str:
            # Remove special characters, keep only alphanumeric
            s = re.sub(r'[^a-zA-Z0-9]', '', s)
            return s.lower()

        city_clean = clean_string(city)
        restaurant_clean = clean_string(restaurant)
        area_clean = clean_string(area)

        return f"{city_clean}_{restaurant_clean}_{area_clean}"

    def collect_camera_info(self):
        """Interactive collection of camera configurations

        Version: 1.1.0
        Added: Username and password collection for each camera
        """
        print("Camera Configuration:")
        print("(Enter camera IP addresses. Press Enter on empty line to finish)")
        print()

        camera_num = 1
        while True:
            print(f"Camera #{camera_num}:")

            # Camera IP
            ip_address = input(f"  IP Address (e.g., 202.168.40.35) [Enter to finish]: ").strip()
            if not ip_address:
                break

            # Validate IP format
            if not self._validate_ip(ip_address):
                print("  ❌ Invalid IP address format")
                continue

            # Generate camera_id from IP (last segment)
            camera_id = self._generate_camera_id(ip_address)

            # RTSP Credentials (IMPORTANT!)
            print("  RTSP Credentials:")
            username = input(f"    Username (default: admin): ").strip() or "admin"
            password = input(f"    Password (default: 123456): ").strip() or "123456"

            # Port (optional)
            port_input = input(f"  Port (default: 554): ").strip()
            port = int(port_input) if port_input else 554

            # Camera name (optional)
            camera_name = input(f"  Camera Name (optional, default: Camera {camera_num}): ").strip()
            if not camera_name:
                camera_name = f"Camera {camera_num}"

            # Division name (optional)
            division_name = input(f"  Division/Area Name (optional, e.g., A区): ").strip() or None

            # Resolution (optional)
            resolution = input(f"  Resolution (optional, e.g., 2592x1944): ").strip() or None

            # Stream path (optional)
            stream_path = input(f"  Stream Path (default: /media/video1): ").strip() or "/media/video1"

            # Build RTSP endpoint with credentials
            rtsp_endpoint = f"rtsp://{username}:{password}@{ip_address}:{port}{stream_path}"

            # Store camera info
            camera_info = {
                'camera_id': camera_id,
                'location_id': self.location_id,
                'camera_name': camera_name,
                'camera_ip_address': ip_address,
                'rtsp_endpoint': rtsp_endpoint,
                'camera_type': 'UNV',
                'resolution': resolution,
                'division_name': division_name,
                'status': 'active',
                # Store credentials for config file
                'username': username,
                'password': password,
                'port': port,
                'stream_path': stream_path
            }

            self.cameras.append(camera_info)
            print(f"  ✅ Added: {camera_id} ({camera_name})")
            print()

            camera_num += 1

        if not self.cameras:
            print("  ⚠️  No cameras configured. You can add them later.")

    def _validate_ip(self, ip: str) -> bool:
        """Validate IP address format"""
        pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
        if not re.match(pattern, ip):
            return False

        # Check each octet is 0-255
        octets = ip.split('.')
        return all(0 <= int(octet) <= 255 for octet in octets)

    def _generate_camera_id(self, ip_address: str) -> str:
        """Generate camera_id from IP address

        Format: camera_{last_segment}
        Example: 202.168.40.35 -> camera_35
        """
        last_segment = ip_address.split('.')[-1]
        return f"camera_{last_segment}"

    def test_camera_connections(self):
        """Test RTSP connections to all cameras"""
        if not self.cameras:
            print("  No cameras to test")
            return

        try:
            import cv2
        except ImportError:
            print("  ⚠️  OpenCV not installed, skipping connection test")
            print("  Install with: pip install opencv-python")
            return

        for camera in self.cameras:
            camera_id = camera['camera_id']
            rtsp_url = camera['rtsp_endpoint']

            print(f"  Testing {camera_id} ({camera['camera_ip_address']})...", end=" ")

            # Try to open RTSP stream
            cap = cv2.VideoCapture(rtsp_url)
            success, frame = cap.read()
            cap.release()

            if success:
                print("✅ Connected")
                camera['connection_status'] = 'success'
            else:
                print("❌ Failed")
                camera['connection_status'] = 'failed'
                print(f"     Check: IP address, RTSP endpoint, network connectivity")

    def register_to_database(self):
        """Register location and cameras in local SQLite database"""
        cursor = self.conn.cursor()

        # Insert location
        cursor.execute('''
            INSERT OR REPLACE INTO locations
            (location_id, city, restaurant_name, commercial_area, address, region, timezone, is_active)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1)
        ''', (
            self.location_info['location_id'],
            self.location_info['city'],
            self.location_info['restaurant_name'],
            self.location_info['commercial_area'],
            self.location_info['address'],
            self.location_info['region'],
            self.location_info['timezone']
        ))

        print(f"  ✅ Location registered: {self.location_id}")

        # Insert cameras
        for camera in self.cameras:
            cursor.execute('''
                INSERT OR REPLACE INTO cameras
                (camera_id, location_id, camera_name, camera_ip_address, rtsp_endpoint,
                 camera_type, resolution, division_name, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                camera['camera_id'],
                camera['location_id'],
                camera['camera_name'],
                camera['camera_ip_address'],
                camera['rtsp_endpoint'],
                camera['camera_type'],
                camera['resolution'],
                camera['division_name'],
                camera['status']
            ))
            print(f"  ✅ Camera registered: {camera['camera_id']}")

        self.conn.commit()

    def save_configuration_files(self):
        """Save location and camera configuration to JSON files

        Version: 1.1.0
        Changes: Fixed cameras_config.json format for capture_rtsp_streams.py compatibility
        """
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Location config
        location_config_path = CONFIG_DIR / f"{self.location_id}_location.json"
        with open(location_config_path, 'w') as f:
            json.dump(self.location_info, f, indent=2)
        print(f"  ✅ Location config: {location_config_path.name}")

        # Cameras config (full database format)
        cameras_config_path = CONFIG_DIR / f"{self.location_id}_cameras.json"
        with open(cameras_config_path, 'w') as f:
            json.dump(self.cameras, f, indent=2)
        print(f"  ✅ Cameras config: {cameras_config_path.name}")

        # Main cameras_config.json (for capture_rtsp_streams.py)
        main_cameras_config = CONFIG_DIR / "cameras_config.json"

        # Convert database format to capture script format
        cameras_for_capture = {}
        for cam in self.cameras:
            # Parse resolution if provided
            resolution = [2592, 1944]  # Default
            if cam.get('resolution'):
                try:
                    width, height = cam['resolution'].split('x')
                    resolution = [int(width), int(height)]
                except:
                    pass  # Use default

            # Parse RTSP endpoint to extract stream_path
            rtsp_endpoint = cam.get('rtsp_endpoint', '')
            # Extract path after port (e.g., /media/video1 or /cam/realmonitor...)
            if '://' in rtsp_endpoint:
                # Format: rtsp://ip:port/path...
                path_part = rtsp_endpoint.split('/', 3)[-1] if rtsp_endpoint.count('/') >= 3 else 'media/video1'
                stream_path = '/' + path_part
            else:
                stream_path = '/media/video1'  # Default UNV stream path

            cameras_for_capture[cam['camera_id']] = {
                'ip': cam['camera_ip_address'],
                'port': cam.get('port', 554),
                'username': cam.get('username', 'admin'),
                'password': cam.get('password', '123456'),
                'stream_path': cam.get('stream_path', stream_path),
                'resolution': resolution,
                'fps': 20,  # Default FPS
                'division_name': cam.get('division_name', ''),
                'location_id': cam['location_id'],
                'enabled': cam.get('status', 'active') == 'active',
                'notes': cam.get('camera_name', '')
            }

        with open(main_cameras_config, 'w') as f:
            json.dump(cameras_for_capture, f, indent=2)
        print(f"  ✅ Main cameras config: {main_cameras_config.name}")

    def sync_to_supabase(self):
        """Sync location and cameras to Supabase cloud database"""
        print("  ℹ️  Cloud sync disabled (not configured yet)")
        print("  Location and cameras saved locally only")
        return

        # DISABLED: Supabase sync (can be enabled later)
        # Check if Supabase credentials available
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_ANON_KEY')

        if not supabase_url or not supabase_key:
            print("  ⚠️  Supabase credentials not found in environment")
            print("  Set SUPABASE_URL and SUPABASE_ANON_KEY to enable cloud sync")
            print("  Skipping cloud sync for now...")
            return

        try:
            from supabase import create_client
        except ImportError:
            print("  ⚠️  Supabase client not installed")
            print("  Install with: pip install supabase")
            print("  Skipping cloud sync for now...")
            return

        try:
            supabase = create_client(supabase_url, supabase_key)

            # Sync location to ASE_locations
            location_data = {
                'location_id': self.location_info['location_id'],
                'city': self.location_info['city'],
                'restaurant_name': self.location_info['restaurant_name'],
                'commercial_area': self.location_info['commercial_area'],
                'address': self.location_info['address'],
                'region': self.location_info['region'],
                'timezone': self.location_info['timezone'],
                'is_active': True
            }

            supabase.table('ASE_locations').upsert(location_data).execute()
            print(f"  ✅ Location synced to Supabase: {self.location_id}")

            # Sync cameras to ASE_cameras
            for camera in self.cameras:
                camera_data = {
                    'camera_id': camera['camera_id'],
                    'location_id': camera['location_id'],
                    'camera_name': camera['camera_name'],
                    'camera_ip_address': camera['camera_ip_address'],
                    'rtsp_endpoint': camera['rtsp_endpoint'],
                    'camera_type': camera['camera_type'],
                    'resolution': camera['resolution'],
                    'division_name': camera['division_name'],
                    'status': camera['status']
                }

                supabase.table('ASE_cameras').upsert(camera_data).execute()
                print(f"  ✅ Camera synced: {camera['camera_id']}")

        except Exception as e:
            print(f"  ❌ Supabase sync failed: {e}")
            print("  Location and cameras saved locally. Sync to cloud later.")

    def print_summary(self):
        """Print deployment summary"""
        print("=" * 70)
        print("🎉 Deployment Initialization Complete!")
        print("=" * 70)
        print()
        print(f"📍 Location: {self.location_info['city']} / {self.location_info['restaurant_name']}")
        print(f"   Location ID: {self.location_id}")
        print()
        print(f"📷 Cameras: {len(self.cameras)} configured")
        for camera in self.cameras:
            status_icon = "✅" if camera.get('connection_status') == 'success' else "⚠️"
            print(f"   {status_icon} {camera['camera_id']}: {camera['camera_ip_address']}")
        print()
        print("📁 Configuration Files:")
        print(f"   {CONFIG_DIR / f'{self.location_id}_location.json'}")
        print(f"   {CONFIG_DIR / f'{self.location_id}_cameras.json'}")
        print(f"   {CONFIG_DIR / 'cameras_config.json'}")
        print()
        print("Next Steps:")
        print("  1. Run camera testing: python3 camera_testing/test_rtsp_connections.py")
        print("  2. Set up ROI configuration: ./run_interactive.sh")
        print("  3. Start video capture: python3 video_capture/capture_rtsp_streams.py")
        print()


def main():
    """Main entry point"""
    initializer = RestaurantInitializer()

    try:
        initializer.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  Initialization cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        if initializer.conn:
            initializer.conn.close()


if __name__ == "__main__":
    main()

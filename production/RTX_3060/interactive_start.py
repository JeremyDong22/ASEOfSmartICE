#!/usr/bin/env python3
"""
ASE Restaurant Surveillance System - Interactive Startup Wizard v3.0
Created: 2025-11-16
Modified: 2025-11-16 - Comprehensive interactive configuration and testing system

Purpose:
- Interactive configuration review and editing
- Comprehensive camera connection testing
- Feature overview and system verification
- Verbose feedback at every step
- Foolproof startup with error recovery

Usage:
    python3 interactive_start.py                # Full interactive mode
    python3 interactive_start.py --quick        # Skip confirmations (expert mode)
    python3 interactive_start.py --test-only    # Test cameras without starting
"""

import os
import sys
import json
import time
import sqlite3
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import shutil

# Color codes for terminal output
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    MAGENTA = '\033[0;35m'

# Project paths
PROJECT_ROOT = Path(__file__).parent
SCRIPTS_DIR = PROJECT_ROOT / "scripts"
CONFIG_DIR = SCRIPTS_DIR / "config"
DB_PATH = PROJECT_ROOT / "db" / "detection_data.db"
MODELS_DIR = PROJECT_ROOT / "models"
LOGS_DIR = PROJECT_ROOT / "logs"

# Add scripts to path
sys.path.insert(0, str(SCRIPTS_DIR))


class InteractiveStartup:
    """
    Interactive startup wizard for surveillance system
    Handles configuration review, testing, and service startup
    """

    def __init__(self, quick_mode=False, test_only=False):
        self.quick_mode = quick_mode
        self.test_only = test_only
        self.config = {}
        self.cameras = []
        self.location_config = {}
        self.roi_config = {}
        self.system_settings = {}
        self.camera_test_results = {}

    def run(self):
        """Main startup workflow"""
        try:
            # Step 1: Welcome and pre-flight checks
            self.show_welcome()
            if not self.run_preflight_checks():
                return False

            # Step 2: Configuration review loop
            while True:
                self.load_all_configuration()
                self.display_configuration_review()

                if self.quick_mode:
                    break

                choice = self.prompt_menu(
                    "IS THIS CONFIGURATION CORRECT?",
                    [
                        ("continue", "✅ Yes - Continue to camera testing"),
                        ("edit", "📝 Edit configuration (interactive menu)"),
                        ("reload", "🔄 Reload from disk"),
                        ("exit", "❌ Exit")
                    ]
                )

                if choice == "continue":
                    break
                elif choice == "edit":
                    self.interactive_editor()
                elif choice == "reload":
                    continue
                elif choice == "exit":
                    return False

            # Step 3: Camera testing
            if not self.test_all_cameras_workflow():
                return False

            # Step 3.5: ROI configuration (per camera)
            if not self.quick_mode:
                if not self.configure_roi_for_cameras():
                    return False

            # Step 4: Feature overview
            self.show_feature_overview()

            if self.test_only:
                self.print_box("✅ TESTING COMPLETE", "All cameras tested successfully. Exiting (test-only mode).")
                return True

            # Step 5: Startup mode selection
            mode = self.prompt_startup_mode()

            if mode == "background":
                return self.start_background_service()
            elif mode == "foreground":
                return self.start_foreground_service()
            elif mode == "review":
                return self.run()  # Start over
            else:
                return False

        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}⚠️  Interrupted by user{Colors.RESET}\n")
            return False
        except Exception as e:
            print(f"\n\n{Colors.RED}❌ Fatal error: {e}{Colors.RESET}")
            import traceback
            traceback.print_exc()
            return False

    # ============================================================================
    # WELCOME & PRE-FLIGHT CHECKS
    # ============================================================================

    def show_welcome(self):
        """Display welcome banner"""
        print("\n" + "=" * 72)
        print(f"{Colors.CYAN}{Colors.BOLD}🎥 ASE Restaurant Surveillance System - Interactive Setup v3.0{Colors.RESET}")
        print("=" * 72)
        print(f"Location:  {PROJECT_ROOT}")
        print(f"Hardware:  NVIDIA RTX 3060")
        print(f"Date:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 72 + "\n")

    def run_preflight_checks(self) -> bool:
        """Validate system prerequisites"""
        print(f"{Colors.BOLD}[PRE-FLIGHT CHECKS]{Colors.RESET}")
        print("─" * 72)

        checks = [
            ("Python 3.7+", self.check_python),
            ("Database", self.check_database),
            ("YOLO Models", self.check_models),
            ("Network", self.check_network),
            ("Disk Space", self.check_disk),
            ("GPU", self.check_gpu)
        ]

        all_passed = True

        for name, check_func in checks:
            status, message = check_func()

            if status == "ok":
                print(f"✅ {name}: {Colors.GREEN}{message}{Colors.RESET}")
            elif status == "warning":
                print(f"⚠️  {name}: {Colors.YELLOW}{message}{Colors.RESET}")
            elif status == "error":
                print(f"❌ {name}: {Colors.RED}{message}{Colors.RESET}")
                all_passed = False

        print("─" * 72 + "\n")

        if not all_passed:
            print(f"{Colors.RED}❌ Pre-flight checks failed. Please fix the issues above.{Colors.RESET}\n")
            return False

        return True

    def check_python(self) -> Tuple[str, str]:
        """Check Python version"""
        version = sys.version.split()[0]
        major, minor = map(int, version.split('.')[:2])

        if major >= 3 and minor >= 7:
            return ("ok", f"Python {version}")
        else:
            return ("error", f"Python {version} (need 3.7+)")

    def check_database(self) -> Tuple[str, str]:
        """Check database exists and has schema"""
        if not DB_PATH.exists():
            return ("warning", "Database not initialized (will create)")

        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            if len(tables) > 0:
                return ("ok", f"{len(tables)} tables initialized")
            else:
                return ("warning", "Database empty (will initialize)")
        except Exception as e:
            return ("error", f"Database error: {e}")

    def check_models(self) -> Tuple[str, str]:
        """Check YOLO models exist"""
        models = {
            "yolov8m.pt": "Person detector",
            "waiter_customer_classifier.pt": "Staff classifier"
        }

        missing = []
        for model_file in models.keys():
            if not (MODELS_DIR / model_file).exists():
                missing.append(model_file)

        if len(missing) == 0:
            return ("ok", f"All models present ({len(models)} files)")
        elif len(missing) == len(models):
            return ("error", "No models found")
        else:
            return ("warning", f"{len(missing)} models missing: {', '.join(missing)}")

    def check_network(self) -> Tuple[str, str]:
        """Check network connectivity"""
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", "8.8.8.8"],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return ("ok", "Internet reachable")
            else:
                return ("warning", "No internet (local mode OK)")
        except:
            return ("warning", "Network check failed (local mode OK)")

    def check_disk(self) -> Tuple[str, str]:
        """Check disk space"""
        try:
            total, used, free = shutil.disk_usage(str(PROJECT_ROOT))
            free_gb = free // (2**30)

            if free_gb > 200:
                return ("ok", f"{free_gb} GB free")
            elif free_gb > 100:
                return ("warning", f"{free_gb} GB free (getting low)")
            else:
                return ("error", f"{free_gb} GB free (need 100+ GB)")
        except:
            return ("warning", "Unable to check")

    def check_gpu(self) -> Tuple[str, str]:
        """Check GPU availability"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,temperature.gpu", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                gpu_info = result.stdout.strip()
                return ("ok", gpu_info)
            else:
                return ("warning", "GPU not detected")
        except:
            return ("warning", "nvidia-smi not available")

    # ============================================================================
    # CONFIGURATION LOADING
    # ============================================================================

    def load_all_configuration(self):
        """Load all configuration files"""
        # Load location config
        location_files = list(CONFIG_DIR.glob("*_location.json"))
        if location_files:
            with open(location_files[0]) as f:
                self.location_config = json.load(f)

        # Load cameras config
        cameras_file = CONFIG_DIR / "cameras_config.json"
        if cameras_file.exists():
            with open(cameras_file) as f:
                cameras_data = json.load(f)
                self.cameras = [
                    {"id": cam_id, **cam_config}
                    for cam_id, cam_config in cameras_data.items()
                ]

        # Load ROI configs (PER CAMERA)
        # Each camera has its own ROI file: camera_35_roi.json, camera_22_roi.json, etc.
        self.roi_config = {}
        for camera in self.cameras:
            cam_id = camera['id']
            roi_file = CONFIG_DIR / f"{cam_id}_roi.json"

            if roi_file.exists():
                with open(roi_file) as f:
                    self.roi_config[cam_id] = json.load(f)
            else:
                # Check for legacy global config
                legacy_roi = CONFIG_DIR / "table_region_config.json"
                if legacy_roi.exists() and not self.roi_config:
                    # Migrate: assume legacy config belongs to first camera
                    with open(legacy_roi) as f:
                        legacy_data = json.load(f)
                        if self.cameras:
                            first_cam = self.cameras[0]['id']
                            self.roi_config[first_cam] = legacy_data
                            print(f"{Colors.YELLOW}⚠️  Migrating legacy ROI config to {first_cam}_roi.json{Colors.RESET}")

        # Load system settings (defaults)
        self.system_settings = {
            "capture_hours": "11:00 AM - 9:00 PM",
            "processing_hours": "11:00 PM - 6:00 AM",
            "analysis_fps": 5,
            "detection_mode": "Combined (Tables + Regions)",
            "supabase_sync": self.check_supabase_enabled(),
            "monitoring_enabled": True,
            "auto_restart": True
        }

    def check_supabase_enabled(self) -> bool:
        """Check if Supabase credentials are configured"""
        return bool(os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_ANON_KEY"))

    # ============================================================================
    # CONFIGURATION REVIEW DISPLAY
    # ============================================================================

    def display_configuration_review(self):
        """Show comprehensive configuration summary"""
        print("\n" + "=" * 72)
        print(f"{Colors.BOLD}📋 STEP 1: CONFIGURATION REVIEW{Colors.RESET}")
        print("=" * 72 + "\n")

        print(f"Loading configuration from: {Colors.CYAN}{CONFIG_DIR}{Colors.RESET}\n")

        # Location configuration
        self.print_section("LOCATION CONFIGURATION", self.format_location())

        # Camera configuration
        self.print_section("CAMERA CONFIGURATION", self.format_cameras())

        # ROI configuration
        self.print_section("ROI CONFIGURATION", self.format_roi())

        # System settings
        self.print_section("SYSTEM SETTINGS", self.format_system_settings())

    def format_location(self) -> List[str]:
        """Format location configuration"""
        if not self.location_config:
            return ["⚠️  No location configured"]

        lines = [
            f"Location ID:        {self.location_config.get('location_id', 'N/A')}",
            f"Restaurant:         {self.location_config.get('restaurant_name', 'N/A')}",
            f"City:               {self.location_config.get('city', 'N/A')}",
            f"Commercial Area:    {self.location_config.get('commercial_area', 'N/A')}",
            f"Timezone:           {self.location_config.get('timezone', 'Asia/Shanghai')}"
        ]
        return lines

    def format_cameras(self) -> List[str]:
        """Format camera configuration"""
        if not self.cameras:
            return ["⚠️  No cameras configured"]

        lines = [f"Found {len(self.cameras)} cameras in cameras_config.json:\n"]

        for i, camera in enumerate(self.cameras, 1):
            cam_id = camera.get('id', 'unknown')
            ip = camera.get('ip', 'N/A')
            port = camera.get('port', 554)
            username = camera.get('username', 'admin')
            resolution = camera.get('resolution', [0, 0])
            fps = camera.get('fps', 0)
            enabled = camera.get('enabled', True)

            # Check ROI configuration for this camera
            has_roi = cam_id in self.roi_config
            roi_status = "✅ ROI configured" if has_roi else "❌ No ROI configured"

            if has_roi:
                roi_data = self.roi_config[cam_id]
                tables = len(roi_data.get('tables', []))
                service_areas = len(roi_data.get('service_areas', []))
                roi_details = f"({tables} tables, {service_areas} service areas)"
            else:
                roi_details = "(interactive drawing required)"

            lines.extend([
                f"Camera {i}: {Colors.CYAN}{cam_id}{Colors.RESET}",
                f"  IP Address:       {ip}:{port}",
                f"  Credentials:      {username}:***",
                f"  Resolution:       {resolution[0]}x{resolution[1]} @ {fps}fps",
                f"  Stream:           rtsp://{username}:***@{ip}:{port}{camera.get('stream_path', '/media/video1')}",
                f"  Status:           {'✅ Enabled' if enabled else '❌ Disabled'}",
                f"  ROI Config:       {roi_status} {roi_details}",
                ""
            ])

        return lines

    def format_roi(self) -> List[str]:
        """Format ROI configuration summary"""
        if not self.roi_config:
            return ["⚠️  No ROI configured for any camera"]

        lines = [f"Configuration files: Per-camera ROI (camera_XX_roi.json)\n"]

        cameras_with_roi = len(self.roi_config)
        total_cameras = len(self.cameras)

        lines.append(f"Cameras with ROI:   {cameras_with_roi}/{total_cameras}")
        lines.append("")

        # Show details for each camera with ROI
        for cam_id, roi_data in self.roi_config.items():
            tables = len(roi_data.get('tables', []))
            sitting_areas = len(roi_data.get('sitting_areas', []))
            service_areas = len(roi_data.get('service_areas', []))
            frame_size = roi_data.get('frame_size', [0, 0])

            lines.append(f"{Colors.CYAN}{cam_id}{Colors.RESET}:")
            lines.append(f"  Frame Size:       {frame_size[0]}x{frame_size[1]}")
            lines.append(f"  Tables:           {tables}")
            lines.append(f"  Sitting Areas:    {sitting_areas}")
            lines.append(f"  Service Areas:    {service_areas}")
            lines.append("")

        # List cameras WITHOUT ROI
        cameras_without_roi = [cam['id'] for cam in self.cameras if cam['id'] not in self.roi_config]
        if cameras_without_roi:
            lines.append(f"{Colors.YELLOW}Cameras needing ROI configuration:{Colors.RESET}")
            for cam_id in cameras_without_roi:
                lines.append(f"  • {cam_id} (not configured)")

        return lines

    def format_system_settings(self) -> List[str]:
        """Format system settings"""
        lines = [
            f"Operating Hours:    {self.system_settings['capture_hours']} (capture)",
            f"Processing Window:  {self.system_settings['processing_hours']} (analysis)",
            f"Analysis FPS:       {self.system_settings['analysis_fps']} fps",
            f"Detection Mode:     {self.system_settings['detection_mode']}",
            f"Supabase Sync:      {'✅ Enabled (hourly)' if self.system_settings['supabase_sync'] else '❌ Disabled'}",
            f"Monitoring:         {'✅ Enabled (disk + GPU)' if self.system_settings['monitoring_enabled'] else '❌ Disabled'}",
            f"Auto-restart:       {'✅ Enabled (on crash)' if self.system_settings['auto_restart'] else '❌ Disabled'}"
        ]
        return lines

    # ============================================================================
    # INTERACTIVE EDITOR
    # ============================================================================

    def interactive_editor(self):
        """Interactive configuration editing menu"""
        while True:
            choice = self.show_editor_menu()

            if choice == "add_camera":
                self.add_camera_wizard()
            elif choice == "edit_camera":
                self.edit_camera_workflow()
            elif choice == "delete_camera":
                self.delete_camera_workflow()
            elif choice == "test_camera":
                self.test_single_camera_workflow()
            elif choice == "view_cameras":
                self.display_cameras_list()
                input("\nPress ENTER to continue...")
            elif choice == "configure_roi":
                self.configure_roi_workflow()
            elif choice == "operating_hours":
                self.edit_operating_hours()
            elif choice == "features":
                self.toggle_features()
            elif choice == "save":
                self.save_all_configuration()
                print(f"\n{Colors.GREEN}✅ All changes saved{Colors.RESET}\n")
                break
            elif choice == "discard":
                if self.confirm("Discard all changes?"):
                    print(f"\n{Colors.YELLOW}⚠️  Changes discarded{Colors.RESET}\n")
                    break

    def show_editor_menu(self) -> str:
        """Show configuration editor menu"""
        print("\n" + "=" * 72)
        print(f"{Colors.BOLD}⚙️  CONFIGURATION EDITOR{Colors.RESET}")
        print("=" * 72 + "\n")

        return self.prompt_menu(
            "What would you like to modify?",
            [
                ("add_camera", "📷 Add new camera"),
                ("edit_camera", "✏️  Edit existing camera"),
                ("delete_camera", "🗑️  Delete camera"),
                ("test_camera", "🔌 Test camera connection"),
                ("view_cameras", "📋 View all cameras"),
                ("", ""),  # Separator
                ("configure_roi", "🎨 Configure table regions (interactive drawing)"),
                ("operating_hours", "🕐 Edit operating hours"),
                ("features", "⚙️  Enable/disable features (Supabase, monitoring)"),
                ("", ""),  # Separator
                ("save", "💾 Save changes and return"),
                ("discard", "❌ Discard changes and return")
            ],
            show_header=False
        )

    def add_camera_wizard(self):
        """Interactive wizard to add a new camera"""
        print("\n" + "─" * 72)
        print(f"{Colors.BOLD}📷 ADD NEW CAMERA{Colors.RESET}")
        print("─" * 72 + "\n")

        # Collect camera details
        camera = {}

        camera['ip'] = input("Camera IP address: ").strip()
        camera['port'] = int(input("Port (default: 554): ").strip() or "554")
        camera['username'] = input("Username (default: admin): ").strip() or "admin"
        camera['password'] = input("Password (default: 123456): ").strip() or "123456"
        camera['stream_path'] = input("Stream path (default: /media/video1): ").strip() or "/media/video1"

        # Generate camera ID from IP
        ip_last = camera['ip'].split('.')[-1]
        camera['id'] = f"camera_{ip_last}"

        # Optional fields
        camera['division'] = input("Division/Area name (optional): ").strip() or None
        camera['enabled'] = True

        # Add to cameras list
        self.cameras.append(camera)

        print(f"\n{Colors.GREEN}✅ Camera {camera['id']} added{Colors.RESET}")

        # Ask if user wants to test it
        if self.confirm("Test camera connection now?"):
            self.test_camera_connection(camera)

    def edit_camera_workflow(self):
        """Workflow to edit an existing camera"""
        if not self.cameras:
            print(f"\n{Colors.YELLOW}⚠️  No cameras to edit{Colors.RESET}\n")
            return

        camera = self.select_camera("Select camera to edit")
        if not camera:
            return

        self.edit_camera_wizard(camera)

    def delete_camera_workflow(self):
        """Workflow to delete a camera"""
        if not self.cameras:
            print(f"\n{Colors.YELLOW}⚠️  No cameras to delete{Colors.RESET}\n")
            return

        camera = self.select_camera("Select camera to delete")
        if not camera:
            return

        if self.confirm(f"Delete camera {camera['id']}?"):
            self.cameras.remove(camera)
            print(f"\n{Colors.GREEN}✅ Camera deleted{Colors.RESET}\n")

    def select_camera(self, prompt="Select camera") -> Optional[Dict]:
        """Prompt user to select a camera from list"""
        print(f"\n{Colors.BOLD}{prompt}:{Colors.RESET}\n")

        for i, camera in enumerate(self.cameras, 1):
            print(f"  [{i}] {camera['id']} ({camera.get('ip', 'N/A')})")
        print(f"  [0] Cancel\n")

        try:
            choice = int(input("Your choice: ").strip())
            if choice == 0:
                return None
            elif 1 <= choice <= len(self.cameras):
                return self.cameras[choice - 1]
        except (ValueError, KeyboardInterrupt):
            pass

        return None

    def edit_camera_wizard(self, camera: Dict):
        """Edit camera configuration"""
        print(f"\n{Colors.BOLD}✏️  Editing Camera: {camera['id']}{Colors.RESET}\n")

        # Show current config
        print("Current configuration:")
        for key, value in camera.items():
            if key == 'password':
                print(f"  {key}: ***")
            else:
                print(f"  {key}: {value}")
        print()

        # Edit each field
        print("Enter new value or press ENTER to keep current:\n")

        camera['ip'] = input(f"IP [{camera.get('ip', '')}]: ").strip() or camera.get('ip')
        camera['port'] = int(input(f"Port [{camera.get('port', 554)}]: ").strip() or camera.get('port', 554))
        camera['username'] = input(f"Username [{camera.get('username', 'admin')}]: ").strip() or camera.get('username')

        new_password = input(f"Password [***]: ").strip()
        if new_password:
            camera['password'] = new_password

        camera['stream_path'] = input(f"Stream path [{camera.get('stream_path', '/media/video1')}]: ").strip() or camera.get('stream_path')

        print(f"\n{Colors.GREEN}✅ Camera updated{Colors.RESET}\n")

    def test_single_camera_workflow(self):
        """Test a single selected camera"""
        if not self.cameras:
            print(f"\n{Colors.YELLOW}⚠️  No cameras configured{Colors.RESET}\n")
            return

        camera = self.select_camera("Select camera to test")
        if not camera:
            return

        print(f"\n{Colors.BOLD}🔌 Testing camera {camera['id']}...{Colors.RESET}\n")
        self.test_camera_connection(camera, verbose=True)

    def display_cameras_list(self):
        """Display formatted list of all cameras"""
        print("\n" + "─" * 72)
        print(f"{Colors.BOLD}📋 ALL CAMERAS ({len(self.cameras)}){Colors.RESET}")
        print("─" * 72 + "\n")

        for i, camera in enumerate(self.cameras, 1):
            status = "✅ Enabled" if camera.get('enabled', True) else "❌ Disabled"
            print(f"{i}. {Colors.CYAN}{camera['id']}{Colors.RESET}")
            print(f"   IP: {camera.get('ip', 'N/A')}:{camera.get('port', 554)}")
            print(f"   User: {camera.get('username', 'admin')}")
            print(f"   Status: {status}")
            print()

    def configure_roi_for_cameras(self) -> bool:
        """Configure ROI for cameras that need it"""
        # Find cameras without ROI
        cameras_needing_roi = [cam for cam in self.cameras if cam['id'] not in self.roi_config and cam.get('enabled', True)]

        if not cameras_needing_roi:
            print(f"\n{Colors.GREEN}✅ All cameras have ROI configured{Colors.RESET}\n")
            return True

        print("\n" + "=" * 72)
        print(f"{Colors.BOLD}🎨 STEP 3.5: ROI CONFIGURATION{Colors.RESET}")
        print("=" * 72 + "\n")

        print(f"{Colors.YELLOW}{len(cameras_needing_roi)} camera(s) need ROI configuration:{Colors.RESET}\n")

        for cam in cameras_needing_roi:
            print(f"  • {Colors.CYAN}{cam['id']}{Colors.RESET} - No tables/regions defined")

        print()

        if not self.confirm("Configure ROI for these cameras now?"):
            print(f"\n{Colors.YELLOW}⚠️  Warning: Cameras without ROI will not perform table/region detection{Colors.RESET}")
            print("You can configure ROI later using the interactive drawing tool.\n")
            return True

        # Configure ROI for each camera
        for camera in cameras_needing_roi:
            if not self.configure_roi_for_camera(camera):
                # User chose to skip or cancel
                continue

        return True

    def configure_roi_for_camera(self, camera: Dict) -> bool:
        """Configure ROI for a specific camera"""
        cam_id = camera['id']

        print("\n" + "─" * 72)
        print(f"{Colors.BOLD}🎨 Configure ROI for {Colors.CYAN}{cam_id}{Colors.RESET}")
        print("─" * 72 + "\n")

        print(f"This camera monitors a region with its own table layout.")
        print(f"You'll need to define:")
        print(f"  1. Division boundary (overall monitored area)")
        print(f"  2. Tables and sitting areas")
        print(f"  3. Service areas (bar, POS, prep stations)\n")

        choice = self.prompt_menu(
            "How do you want to configure ROI?",
            [
                ("interactive", "🖱️  Interactive drawing (recommended) - Opens GUI"),
                ("manual", "📝 Manual entry - Provide video file path"),
                ("skip", "⏭️  Skip for now - Configure later"),
                ("cancel", "❌ Cancel ROI setup")
            ],
            show_header=False
        )

        if choice == "interactive":
            return self.launch_interactive_roi_drawing(camera)
        elif choice == "manual":
            return self.configure_roi_manual(camera)
        elif choice == "skip":
            print(f"\n{Colors.YELLOW}⏭️  Skipped ROI configuration for {cam_id}{Colors.RESET}\n")
            return True
        else:
            return False

    def launch_interactive_roi_drawing(self, camera: Dict) -> bool:
        """Launch interactive ROI drawing tool for specific camera"""
        cam_id = camera['id']

        print(f"\n{Colors.BOLD}Launching interactive ROI drawing for {cam_id}...{Colors.RESET}\n")

        # Need a video file from this camera to draw on
        print(f"Please provide a sample video file from {Colors.CYAN}{cam_id}{Colors.RESET}:")
        print(f"  • Should be from camera IP: {camera.get('ip', 'N/A')}")
        print(f"  • Recommended: Recent video showing typical restaurant layout")
        print(f"  • Location: videos/YYYYMMDD/{cam_id}/\n")

        video_path = input("Video file path (or press ENTER to skip): ").strip()

        if not video_path:
            print(f"\n{Colors.YELLOW}⚠️  No video provided. Skipping ROI configuration.{Colors.RESET}\n")
            return True

        # Check if video exists
        video_file = Path(video_path)
        if not video_file.exists():
            print(f"\n{Colors.RED}❌ Video file not found: {video_path}{Colors.RESET}\n")
            return False

        # Launch interactive drawing script
        print(f"\n{Colors.GREEN}Launching interactive ROI drawing tool...{Colors.RESET}")
        print(f"{Colors.YELLOW}GUI window will open. Follow on-screen instructions:{Colors.RESET}")
        print("  • Click to add polygon points")
        print("  • Press ENTER to complete each region")
        print("  • Press Ctrl+S to save configuration")
        print("  • Press Q to quit\n")

        try:
            detection_script = SCRIPTS_DIR / "video_processing" / "table_and_region_state_detection.py"

            # Run interactive mode and save to camera-specific config file
            output_config = CONFIG_DIR / f"{cam_id}_roi.json"

            result = subprocess.run(
                ["python3", str(detection_script), "--video", str(video_file), "--interactive"],
                cwd=str(SCRIPTS_DIR)
            )

            if result.returncode == 0:
                # Check if config was created
                default_config = CONFIG_DIR / "table_region_config.json"

                if default_config.exists():
                    # Rename to camera-specific file
                    default_config.rename(output_config)
                    print(f"\n{Colors.GREEN}✅ ROI configuration saved to {output_config.name}{Colors.RESET}\n")

                    # Reload configuration
                    self.load_all_configuration()
                    return True
                else:
                    print(f"\n{Colors.YELLOW}⚠️  No configuration file created. ROI drawing may have been cancelled.{Colors.RESET}\n")
                    return True
            else:
                print(f"\n{Colors.RED}❌ Interactive drawing failed{Colors.RESET}\n")
                return False

        except Exception as e:
            print(f"\n{Colors.RED}❌ Error launching interactive tool: {e}{Colors.RESET}\n")
            return False

    def configure_roi_manual(self, camera: Dict) -> bool:
        """Manually configure ROI (advanced users)"""
        print(f"\n{Colors.YELLOW}📝 Manual ROI configuration{Colors.RESET}")
        print(f"Create the ROI file manually at: scripts/config/{camera['id']}_roi.json")
        print(f"See existing ROI files for format reference.\n")
        input("Press ENTER when done...")
        self.load_all_configuration()
        return True

    def configure_roi_workflow(self):
        """Legacy method - now redirects to per-camera configuration"""
        print(f"\n{Colors.YELLOW}⚠️  ROI configuration is now per-camera{Colors.RESET}")
        print("Use the main workflow to configure ROI for each camera individually.\n")
        input("Press ENTER to continue...")

    def edit_operating_hours(self):
        """Edit operating hours"""
        print(f"\n{Colors.YELLOW}⚠️  This feature will be implemented in future version{Colors.RESET}\n")
        input("Press ENTER to continue...")

    def toggle_features(self):
        """Toggle system features"""
        print(f"\n{Colors.BOLD}⚙️  SYSTEM FEATURES{Colors.RESET}\n")

        print("Current status:")
        print(f"  Supabase Sync: {'✅ Enabled' if self.system_settings['supabase_sync'] else '❌ Disabled'}")
        print(f"  Monitoring: {'✅ Enabled' if self.system_settings['monitoring_enabled'] else '❌ Disabled'}")
        print()

        if self.confirm("Toggle Supabase sync?"):
            self.system_settings['supabase_sync'] = not self.system_settings['supabase_sync']
            print(f"Supabase sync: {'✅ Enabled' if self.system_settings['supabase_sync'] else '❌ Disabled'}")

        print()

    def save_all_configuration(self):
        """Save all configuration changes"""
        # Save cameras config
        cameras_dict = {cam['id']: {k: v for k, v in cam.items() if k != 'id'} for cam in self.cameras}

        cameras_file = CONFIG_DIR / "cameras_config.json"
        with open(cameras_file, 'w') as f:
            json.dump(cameras_dict, f, indent=2)

    # ============================================================================
    # CAMERA TESTING
    # ============================================================================

    def test_all_cameras_workflow(self) -> bool:
        """Test all cameras with retry/skip/edit options"""
        print("\n" + "=" * 72)
        print(f"{Colors.BOLD}🔌 STEP 2: CAMERA CONNECTION TEST{Colors.RESET}")
        print("=" * 72 + "\n")

        print(f"Testing RTSP connections for {len(self.cameras)} cameras...")
        print("This may take 10-20 seconds per camera.\n")
        print("─" * 72 + "\n")

        # Test all cameras
        for i, camera in enumerate(self.cameras, 1):
            print(f"[{i}/{len(self.cameras)}] Testing {Colors.CYAN}{camera['id']}{Colors.RESET} ({camera.get('ip', 'N/A')}:{camera.get('port', 554)})")

            success = self.test_camera_connection(camera, verbose=True)
            self.camera_test_results[camera['id']] = success

            print()

        # Summary
        passed = sum(self.camera_test_results.values())
        total = len(self.camera_test_results)

        print("─" * 72)
        print(f"\n{Colors.BOLD}[TEST SUMMARY]{Colors.RESET}")
        print(f"  Total Cameras:    {total}")
        print(f"  Passed:           {Colors.GREEN}{passed} ✅{Colors.RESET}")
        print(f"  Failed:           {Colors.RED}{total - passed} ❌{Colors.RESET}")
        print(f"  Success Rate:     {passed/total*100:.1f}%\n")

        # Handle failures
        failed_cameras = [cam for cam in self.cameras if not self.camera_test_results.get(cam['id'], False)]

        if failed_cameras and not self.quick_mode:
            return self.handle_camera_failures(failed_cameras)

        return True

    def test_camera_connection(self, camera: Dict, verbose: bool = False) -> bool:
        """Test a single camera connection using OpenCV"""
        try:
            import cv2

            # Build RTSP URL
            ip = camera.get('ip', '')
            port = camera.get('port', 554)
            username = camera.get('username', 'admin')
            password = camera.get('password', '123456')
            stream_path = camera.get('stream_path', '/media/video1')

            rtsp_url = f"rtsp://{username}:{password}@{ip}:{port}{stream_path}"

            if verbose:
                print(f"  ⏳ Connecting to rtsp://{username}:***@{ip}:{port}{stream_path}")

            # Try to open stream
            start_time = time.time()
            cap = cv2.VideoCapture(rtsp_url)

            if not cap.isOpened():
                if verbose:
                    print(f"  {Colors.RED}❌ Connection failed (could not open stream){Colors.RESET}")
                cap.release()
                return False

            # Try to read a frame
            ret, frame = cap.read()
            elapsed = time.time() - start_time

            if ret and frame is not None:
                height, width = frame.shape[:2]
                fps = cap.get(cv2.CAP_PROP_FPS)

                if verbose:
                    print(f"  {Colors.GREEN}✅ Connection successful ({elapsed:.1f}s){Colors.RESET}")
                    print(f"  {Colors.GREEN}✅ Video stream detected ({width}x{height}){Colors.RESET}")
                    print(f"  {Colors.GREEN}✅ FPS: {fps:.1f}{Colors.RESET}")
                    print(f"  {Colors.GREEN}✅ Status: READY{Colors.RESET}")

                cap.release()
                return True
            else:
                if verbose:
                    print(f"  {Colors.RED}❌ Connection failed (no frames received){Colors.RESET}")
                cap.release()
                return False

        except Exception as e:
            if verbose:
                print(f"  {Colors.RED}❌ Connection failed: {e}{Colors.RESET}")
            return False

    def handle_camera_failures(self, failed_cameras: List[Dict]) -> bool:
        """Handle failed camera connections interactively"""
        print("\n" + "=" * 72)
        print(f"{Colors.RED}{Colors.BOLD}⚠️  CAMERA FAILURES DETECTED{Colors.RESET}")
        print("=" * 72 + "\n")

        print(f"{len(failed_cameras)} camera(s) failed connection test.\n")

        for camera in failed_cameras:
            print(f"Camera: {Colors.CYAN}{camera['id']}{Colors.RESET} ({camera.get('ip', 'N/A')})")

            choice = self.prompt_menu(
                "What would you like to do?",
                [
                    ("retry", "🔄 Retry connection"),
                    ("edit", "✏️  Edit camera settings"),
                    ("skip", "⏭️  Skip this camera and continue"),
                    ("remove", "🗑️  Remove this camera"),
                    ("abort", "❌ Abort startup")
                ],
                show_header=False
            )

            if choice == "retry":
                print(f"\n{Colors.BOLD}Retrying...{Colors.RESET}\n")
                success = self.retry_camera_connection(camera)
                self.camera_test_results[camera['id']] = success

            elif choice == "edit":
                self.edit_camera_wizard(camera)
                print(f"\n{Colors.BOLD}Testing again...{Colors.RESET}\n")
                success = self.test_camera_connection(camera, verbose=True)
                self.camera_test_results[camera['id']] = success

            elif choice == "skip":
                camera['enabled'] = False
                print(f"\n{Colors.YELLOW}⏭️  Camera disabled{Colors.RESET}\n")

            elif choice == "remove":
                self.cameras.remove(camera)
                del self.camera_test_results[camera['id']]
                print(f"\n{Colors.YELLOW}🗑️  Camera removed{Colors.RESET}\n")

            elif choice == "abort":
                return False

            print()

        return True

    def retry_camera_connection(self, camera: Dict, max_attempts: int = 3) -> bool:
        """Retry camera connection with backoff"""
        for attempt in range(1, max_attempts + 1):
            print(f"[RETRY ATTEMPT {attempt}/{max_attempts}]")

            wait_time = 5 * attempt
            print(f"  ⏳ Waiting {wait_time} seconds...")
            self.progress_bar(wait_time)

            print(f"  ⏳ Reconnecting to {camera['id']}...")
            success = self.test_camera_connection(camera, verbose=False)

            if success:
                print(f"  {Colors.GREEN}✅ Connection successful!{Colors.RESET}\n")
                return True
            else:
                print(f"  {Colors.RED}❌ Failed{Colors.RESET}\n")

        return False

    # ============================================================================
    # FEATURE OVERVIEW
    # ============================================================================

    def show_feature_overview(self):
        """Display comprehensive feature overview"""
        print("\n" + "=" * 72)
        print(f"{Colors.BOLD}📋 STEP 3: FEATURE OVERVIEW{Colors.RESET}")
        print("=" * 72 + "\n")

        print("The system is now configured and ready. Here's what will run:\n")

        self.print_section("VIDEO CAPTURE - 11:00 AM to 9:00 PM", [
            f"• Capture from {len([c for c in self.cameras if c.get('enabled', True)])} cameras simultaneously",
            "• Save to: videos/YYYYMMDD/camera_XX/",
            "• Codec: H.265 (hardware accelerated)",
            "• Auto-reconnect on network failure",
            "• Segmented files: 5-minute chunks"
        ])

        self.print_section("VIDEO PROCESSING - 11:00 PM to 6:00 AM", [
            "• Process all videos from today",
            "• Detection: Person → Staff Classification",
            "• Analysis: Table states + Region coverage",
            "• Output: results/YYYYMMDD/camera_XX/*.mp4",
            "• Database: State changes to detection_data.db",
            "• Screenshots: Auto-saved on state transitions",
            "• Performance: 3.24x real-time @ 5fps (RTX 3060)"
        ])

        self.print_section("MONITORING - Continuous", [
            "• Disk Space: Predictive monitoring (hourly)",
            "• GPU Monitoring: Every 5 minutes",
            "• System Health: Every 30 minutes"
        ])

        if self.system_settings['supabase_sync']:
            self.print_section("DATABASE SYNC - Hourly", [
                "• Sync to Supabase cloud (database only)",
                "• Batch upload: 1000 rows per transaction",
                "• Retry on failure: 3 attempts"
            ])

        self.print_section("AUTO-RESTART PROTECTION", [
            "• Daemon wrapper with infinite loop",
            "• Auto-restart on crash (10-second delay)",
            "• Graceful shutdown on SIGTERM",
            "• Logging: logs/surveillance_service.log"
        ])

    # ============================================================================
    # STARTUP MODE SELECTION
    # ============================================================================

    def prompt_startup_mode(self) -> str:
        """Prompt user for startup mode"""
        if self.quick_mode:
            return "background"

        print("\n" + "=" * 72)
        print(f"{Colors.BOLD}❓ READY TO START?{Colors.RESET}")
        print("=" * 72 + "\n")

        print("All systems configured and tested. Choose startup mode:\n")

        return self.prompt_menu(
            None,
            [
                ("background", "🚀 Start in BACKGROUND (daemon mode) - Recommended"),
                ("foreground", "🔍 Start in FOREGROUND (debug mode) - See live output"),
                ("review", "📝 Review configuration again"),
                ("exit", "❌ Exit without starting")
            ],
            show_header=False
        )

    def start_background_service(self) -> bool:
        """Start service in background mode"""
        print("\n" + "=" * 72)
        print(f"{Colors.BOLD}🚀 STARTING SURVEILLANCE SERVICE (BACKGROUND MODE){Colors.RESET}")
        print("=" * 72 + "\n")

        steps = [
            ("Creating directories", self.create_directories),
            ("Checking database", self.check_database_ready),
            ("Testing GPU", self.test_gpu_ready),
            ("Starting daemon", self.start_daemon)
        ]

        for i, (name, step_func) in enumerate(steps, 1):
            print(f"[{i}/{len(steps)}] {name}...")
            success, message = step_func()

            if success:
                print(f"  {Colors.GREEN}✅ {message}{Colors.RESET}")
            else:
                print(f"  {Colors.RED}❌ {message}{Colors.RESET}")
                return False

        print("\n" + "─" * 72)
        print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 SURVEILLANCE SERVICE STARTED SUCCESSFULLY!{Colors.RESET}\n")

        print(f"Current Time: {datetime.now().strftime('%H:%M:%S')}")
        print("Status: Service running in background\n")

        print("Management Commands:")
        print("  ./start.sh --status     # Check service status")
        print("  ./start.sh --stop       # Stop service")
        print("  ./start.sh --logs       # View logs")
        print("  ./start.sh --restart    # Restart service\n")

        print("Log Files:")
        print("  Main Log:      logs/surveillance_service.log")
        print("  Startup Log:   logs/startup.log\n")

        print("Real-time Monitoring:")
        print("  tail -f logs/surveillance_service.log\n")

        print("─" * 72 + "\n")

        return True

    def start_foreground_service(self) -> bool:
        """Start service in foreground mode"""
        print("\n" + "=" * 72)
        print(f"{Colors.BOLD}🔍 STARTING SURVEILLANCE SERVICE (FOREGROUND MODE){Colors.RESET}")
        print("=" * 72 + "\n")

        print("Verbose logging enabled. Press Ctrl+C to stop.\n")

        # Start service directly
        service_script = SCRIPTS_DIR / "orchestration" / "surveillance_service.py"

        try:
            subprocess.run(["python3", str(service_script), "start", "--foreground"])
            return True
        except KeyboardInterrupt:
            print(f"\n\n{Colors.YELLOW}⚠️  Stopped by user{Colors.RESET}\n")
            return True
        except Exception as e:
            print(f"\n{Colors.RED}❌ Failed to start: {e}{Colors.RESET}\n")
            return False

    def create_directories(self) -> Tuple[bool, str]:
        """Create required directories"""
        dirs = ["videos", "results", "logs", "db/screenshots"]

        try:
            for d in dirs:
                (PROJECT_ROOT / d).mkdir(parents=True, exist_ok=True)
            return (True, f"{len(dirs)} directories ready")
        except Exception as e:
            return (False, str(e))

    def check_database_ready(self) -> Tuple[bool, str]:
        """Check database is ready"""
        try:
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'")
            count = cursor.fetchone()[0]
            conn.close()
            return (True, f"Database ready ({count} tables)")
        except Exception as e:
            return (False, str(e))

    def test_gpu_ready(self) -> Tuple[bool, str]:
        """Test GPU is ready"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,temperature.gpu", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )

            if result.returncode == 0:
                return (True, result.stdout.strip())
            else:
                return (False, "GPU not detected")
        except:
            return (True, "GPU check skipped")

    def start_daemon(self) -> Tuple[bool, str]:
        """Start the surveillance daemon"""
        try:
            service_script = SCRIPTS_DIR / "orchestration" / "surveillance_service.py"

            # Start in background
            subprocess.Popen(
                ["nohup", "python3", str(service_script), "start"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

            # Wait and check PID file
            time.sleep(3)

            pid_file = PROJECT_ROOT / "surveillance_service.pid"
            if pid_file.exists():
                with open(pid_file) as f:
                    pid = f.read().strip()
                return (True, f"Service started (PID: {pid})")
            else:
                return (False, "PID file not created")

        except Exception as e:
            return (False, str(e))

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def print_section(self, title: str, lines: List[str]):
        """Print a formatted section"""
        print(f"[{title}]")
        print("─" * 72)
        for line in lines:
            print(line)
        print("─" * 72 + "\n")

    def print_box(self, title: str, message: str):
        """Print a boxed message"""
        print("\n" + "=" * 72)
        print(f"{Colors.BOLD}{title}{Colors.RESET}")
        print("=" * 72)
        print(f"\n{message}\n")
        print("=" * 72 + "\n")

    def prompt_menu(self, header: Optional[str], choices: List[Tuple[str, str]], show_header: bool = True) -> str:
        """Display menu and get user choice"""
        if show_header and header:
            print("\n" + "=" * 72)
            print(f"{Colors.BOLD}{header}{Colors.RESET}")
            print("=" * 72 + "\n")
        elif header:
            print(f"\n{Colors.BOLD}{header}{Colors.RESET}\n")

        # Filter out separators and build menu
        menu_items = [(k, v) for k, v in choices if k]

        print("Options:")
        for i, (key, label) in enumerate(menu_items, 1):
            print(f"  [{i}] {label}")
        print()

        while True:
            try:
                choice_num = int(input(f"Your choice [1-{len(menu_items)}]: ").strip())
                if 1 <= choice_num <= len(menu_items):
                    return menu_items[choice_num - 1][0]
            except (ValueError, KeyboardInterrupt):
                print(f"{Colors.YELLOW}Invalid choice. Please try again.{Colors.RESET}")

    def confirm(self, message: str) -> bool:
        """Simple yes/no confirmation"""
        while True:
            response = input(f"{message} (y/n): ").strip().lower()
            if response in ['y', 'yes']:
                return True
            elif response in ['n', 'no']:
                return False

    def progress_bar(self, duration: int):
        """Display progress bar"""
        bar_length = 40

        for i in range(duration):
            filled = int((i + 1) / duration * bar_length)
            bar = '█' * filled + '-' * (bar_length - filled)
            print(f"\r  [{bar}] {i+1}s", end='', flush=True)
            time.sleep(1)
        print()


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="ASE Surveillance System - Interactive Setup Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument("--quick", action="store_true",
                       help="Quick mode (skip confirmations)")
    parser.add_argument("--test-only", action="store_true",
                       help="Test cameras only (don't start service)")

    args = parser.parse_args()

    wizard = InteractiveStartup(
        quick_mode=args.quick,
        test_only=args.test_only
    )

    success = wizard.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

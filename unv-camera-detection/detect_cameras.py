#!/usr/bin/env python3
"""
UNV Camera Detection Tool

Detects Uniview (UNV) IP cameras on the local network using multiple methods:
1. ARP scan for device discovery
2. ONVIF WS-Discovery protocol
3. UNV LAPI REST API for device info
"""

import argparse
import socket
import subprocess
import sys
import json
import concurrent.futures
from dataclasses import dataclass, asdict
from typing import Optional
import ipaddress

try:
    import requests
    from requests.auth import HTTPDigestAuth
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    print("Missing 'requests' library. Install with: pip install requests")
    sys.exit(1)


@dataclass
class CameraInfo:
    """Stores detected camera information"""
    ip: str
    mac: Optional[str] = None
    manufacturer: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    firmware_version: Optional[str] = None
    device_name: Optional[str] = None
    onvif_supported: bool = False
    lapi_accessible: bool = False


class UNVCameraDetector:
    """Detects UNV cameras on the network"""

    # Common ports used by UNV cameras
    CAMERA_PORTS = [80, 443, 554, 8080, 37777]

    # UNV default credentials
    DEFAULT_USERNAME = "admin"
    DEFAULT_PASSWORD = "123456"

    # ONVIF WS-Discovery multicast address and port
    ONVIF_MULTICAST_IP = "239.255.255.250"
    ONVIF_MULTICAST_PORT = 3702

    def __init__(self, username: str = None, password: str = None, timeout: float = 2.0):
        self.username = username or self.DEFAULT_USERNAME
        self.password = password or self.DEFAULT_PASSWORD
        self.timeout = timeout
        self.cameras: list[CameraInfo] = []

    def get_local_network(self) -> str:
        """Get the local network CIDR"""
        try:
            # Get default gateway IP to determine network
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                parts = result.stdout.split()
                if "via" in parts:
                    gateway_idx = parts.index("via") + 1
                    gateway = parts[gateway_idx]
                    # Assume /24 network
                    network = ".".join(gateway.split(".")[:3]) + ".0/24"
                    return network
        except Exception:
            pass
        return "192.168.1.0/24"

    def scan_port(self, ip: str, port: int) -> bool:
        """Check if a port is open on the given IP"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception:
            return False

    def discover_onvif_devices(self) -> list[str]:
        """Discover ONVIF devices using WS-Discovery"""
        discovered_ips = []

        # WS-Discovery probe message
        probe_message = """<?xml version="1.0" encoding="UTF-8"?>
<e:Envelope xmlns:e="http://www.w3.org/2003/05/soap-envelope"
            xmlns:w="http://schemas.xmlsoap.org/ws/2004/08/addressing"
            xmlns:d="http://schemas.xmlsoap.org/ws/2005/04/discovery"
            xmlns:dn="http://www.onvif.org/ver10/network/wsdl">
    <e:Header>
        <w:MessageID>uuid:84ede3de-7dec-11d0-c360-f01234567890</w:MessageID>
        <w:To e:mustUnderstand="true">urn:schemas-xmlsoap-org:ws:2005:04:discovery</w:To>
        <w:Action e:mustUnderstand="true">http://schemas.xmlsoap.org/ws/2005/04/discovery/Probe</w:Action>
    </e:Header>
    <e:Body>
        <d:Probe>
            <d:Types>dn:NetworkVideoTransmitter</d:Types>
        </d:Probe>
    </e:Body>
</e:Envelope>"""

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.settimeout(3)

            # Send discovery probe
            sock.sendto(
                probe_message.encode(),
                (self.ONVIF_MULTICAST_IP, self.ONVIF_MULTICAST_PORT)
            )

            # Collect responses
            while True:
                try:
                    data, addr = sock.recvfrom(65535)
                    ip = addr[0]
                    if ip not in discovered_ips:
                        discovered_ips.append(ip)
                        print(f"  [ONVIF] Discovered device at {ip}")
                except socket.timeout:
                    break

            sock.close()
        except Exception as e:
            print(f"  [ONVIF] Discovery error: {e}")

        return discovered_ips

    def query_lapi(self, ip: str, use_https: bool = False) -> Optional[dict]:
        """Query UNV camera LAPI for device information"""
        protocol = "https" if use_https else "http"
        url = f"{protocol}://{ip}/LAPI/V1.0/System/DeviceBasicInfo"

        try:
            response = requests.get(
                url,
                auth=HTTPDigestAuth(self.username, self.password),
                timeout=self.timeout,
                headers={"Content-Type": "application/json"},
                verify=False
            )

            if response.status_code == 200:
                try:
                    return response.json()
                except Exception:
                    pass
        except Exception:
            pass

        return None

    def check_http_server(self, ip: str) -> Optional[str]:
        """Check HTTP server header for camera identification"""
        for protocol in ["http", "https"]:
            try:
                response = requests.get(
                    f"{protocol}://{ip}/",
                    timeout=self.timeout,
                    allow_redirects=False,
                    verify=False
                )
                server = response.headers.get("Server", "")
                content = response.text.lower()

                # Check server header
                if "uniview" in server.lower() or "unv" in server.lower():
                    return server

                # Check page content for UNV indicators
                if "uniview" in content or "unv" in content or "sslhostip" in content:
                    return "Uniview (detected from page content)"

            except Exception:
                pass
        return None

    def scan_ip(self, ip: str) -> Optional[CameraInfo]:
        """Scan a single IP for UNV camera"""
        # Check if port 80 or 443 is open
        has_http = self.scan_port(ip, 80)
        has_https = self.scan_port(ip, 443)

        if not has_http and not has_https:
            return None

        camera = CameraInfo(ip=ip)

        # Try LAPI query (HTTP first, then HTTPS)
        lapi_data = self.query_lapi(ip, use_https=False)
        if not lapi_data and has_https:
            lapi_data = self.query_lapi(ip, use_https=True)

        if lapi_data:
            camera.lapi_accessible = True
            data = lapi_data.get("Response", {}).get("Data", {})
            camera.manufacturer = data.get("Manufacturer")
            camera.model = data.get("Model")
            camera.serial_number = data.get("SerialNumber")
            camera.firmware_version = data.get("FirmwareVersion")
            camera.device_name = data.get("DeviceName")
            camera.mac = data.get("MACAddress")

            # Only return if it's a UNV/Uniview device
            if camera.manufacturer and "uniview" in camera.manufacturer.lower():
                return camera

        # Check HTTP server header and page content
        server = self.check_http_server(ip)
        if server:
            camera.manufacturer = "Uniview"
            return camera

        return None

    def arp_scan(self) -> list[str]:
        """Get list of IPs from ARP table"""
        ips = []
        try:
            result = subprocess.run(
                ["ip", "neigh", "show"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if line:
                        parts = line.split()
                        if parts and parts[0]:
                            try:
                                ipaddress.ip_address(parts[0])
                                ips.append(parts[0])
                            except ValueError:
                                pass
        except Exception:
            pass
        return ips

    def scan_network(self, network: str = None, use_onvif: bool = True) -> list[CameraInfo]:
        """Scan network for UNV cameras"""
        self.cameras = []
        candidate_ips = set()

        if network is None:
            network = self.get_local_network()

        print(f"\n[*] Scanning network: {network}")

        # Method 1: ONVIF Discovery
        if use_onvif:
            print("\n[1] Running ONVIF WS-Discovery...")
            onvif_ips = self.discover_onvif_devices()
            for ip in onvif_ips:
                candidate_ips.add(ip)

        # Method 2: ARP table
        print("\n[2] Checking ARP table...")
        arp_ips = self.arp_scan()
        print(f"  Found {len(arp_ips)} devices in ARP table")
        for ip in arp_ips:
            candidate_ips.add(ip)

        # Method 3: Scan network range
        print(f"\n[3] Scanning IP range {network}...")
        try:
            net = ipaddress.ip_network(network, strict=False)
            for ip in net.hosts():
                candidate_ips.add(str(ip))
        except ValueError as e:
            print(f"  Invalid network: {e}")

        print(f"\n[*] Checking {len(candidate_ips)} candidate IPs for UNV cameras...")

        # Scan all candidates in parallel
        found_cameras = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            future_to_ip = {executor.submit(self.scan_ip, ip): ip for ip in candidate_ips}
            for future in concurrent.futures.as_completed(future_to_ip):
                result = future.result()
                if result:
                    found_cameras.append(result)
                    print(f"  [+] Found UNV camera: {result.ip} - {result.model or 'Unknown model'}")

        self.cameras = found_cameras
        return self.cameras

    def print_results(self):
        """Print detected cameras in a formatted table"""
        if not self.cameras:
            print("\n[!] No UNV cameras found on the network")
            return

        print(f"\n{'='*80}")
        print(f"  DETECTED UNV CAMERAS ({len(self.cameras)} found)")
        print(f"{'='*80}\n")

        for i, cam in enumerate(self.cameras, 1):
            print(f"Camera {i}:")
            print(f"  IP Address:       {cam.ip}")
            if cam.mac:
                print(f"  MAC Address:      {cam.mac}")
            if cam.manufacturer:
                print(f"  Manufacturer:     {cam.manufacturer}")
            if cam.model:
                print(f"  Model:            {cam.model}")
            if cam.serial_number:
                print(f"  Serial Number:    {cam.serial_number}")
            if cam.firmware_version:
                print(f"  Firmware:         {cam.firmware_version}")
            if cam.device_name:
                print(f"  Device Name:      {cam.device_name}")
            print(f"  LAPI Accessible:  {'Yes' if cam.lapi_accessible else 'No'}")
            print()

    def export_json(self, filename: str):
        """Export results to JSON file"""
        data = [asdict(cam) for cam in self.cameras]
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        print(f"[*] Results exported to {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Detect UNV (Uniview) IP cameras on the network",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Scan default network with auto-detection
  %(prog)s -n 192.168.1.0/24        # Scan specific network
  %(prog)s -u admin -p mypassword   # Use custom credentials
  %(prog)s -o cameras.json          # Export results to JSON
  %(prog)s --no-onvif               # Skip ONVIF discovery
        """
    )

    parser.add_argument(
        "-n", "--network",
        help="Network to scan (CIDR notation, e.g., 192.168.1.0/24)"
    )
    parser.add_argument(
        "-u", "--username",
        default="admin",
        help="Camera username (default: admin)"
    )
    parser.add_argument(
        "-p", "--password",
        default="123456",
        help="Camera password (default: 123456)"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=float,
        default=2.0,
        help="Connection timeout in seconds (default: 2.0)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Export results to JSON file"
    )
    parser.add_argument(
        "--no-onvif",
        action="store_true",
        help="Skip ONVIF WS-Discovery"
    )

    args = parser.parse_args()

    print("""
    ╔═══════════════════════════════════════════╗
    ║     UNV Camera Detection Tool             ║
    ║     Detects Uniview IP cameras            ║
    ╚═══════════════════════════════════════════╝
    """)

    detector = UNVCameraDetector(
        username=args.username,
        password=args.password,
        timeout=args.timeout
    )

    detector.scan_network(
        network=args.network,
        use_onvif=not args.no_onvif
    )

    detector.print_results()

    if args.output:
        detector.export_json(args.output)


if __name__ == "__main__":
    main()

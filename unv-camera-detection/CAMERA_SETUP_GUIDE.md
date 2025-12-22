# UNV Camera Detection and Connection Guide

## Overview

This document records the complete workflow for detecting and connecting to Uniview (UNV) IP cameras on a dedicated surveillance network.

**Date:** December 19, 2025
**Network Type:** Dedicated/Private Surveillance Network
**Total Cameras Found:** 30

---

## Network Topology

```
Internet/Router (192.168.1.1)
        │
        ▼
   PoE Switch
        │
        ├──► UNV NVR (192.168.1.3) ──► Internal PoE Ports ──► 30 Cameras
        │
        ├──► Standalone Cameras (192.168.1.251-254)
        │
        └──► Linux Workstation (192.168.1.12)
```

---

## Step 1: Initial Network Discovery

### Check Network Configuration

```bash
ip addr show
ip route show
```

**Result:** Linux machine connected via `enp4s0` interface on `192.168.1.12/22` subnet (192.168.0.0 - 192.168.3.255).

### Scan ARP Table for Connected Devices

```bash
ip neigh show
```

**Devices Found:**

| IP Address | MAC Address | Device Type |
|------------|-------------|-------------|
| 192.168.1.1 | 30:49:9e:97:b5:d6 | Router/Gateway |
| 192.168.1.3 | 88:26:3F:2c:ea:07 | **UNV NVR** (Uniview MAC) |
| 192.168.1.4 | 68:84:7e:a8:9d:3d | Unknown |
| 192.168.1.251 | 00:61:e6:f6:3d:b9 | Camera |
| 192.168.1.252 | 00:61:45:66:4c:7f | Camera |
| 192.168.1.253 | 00:61:49:a2:02:d5 | Camera |
| 192.168.1.254 | 00:61:88:31:80:31 | Camera |

### Uniview MAC Address Identification

Uniview registered MAC prefixes (OUI):
- `48:EA:63`
- `6C:F1:7E`
- `88:26:3F` ← **Matched NVR at 192.168.1.3**
- `C4:79:05`

---

## Step 2: Port Scanning

### Scan for Web Interfaces (Port 80)

```bash
for ip in $(seq 1 254); do
  timeout 0.5 bash -c "echo >/dev/tcp/192.168.1.$ip/80" 2>/dev/null && echo "192.168.1.$ip"
done
```

**Devices with HTTP:**
- 192.168.1.1 (Router)
- 192.168.1.3 (NVR)
- 192.168.1.12 (Linux PC)
- 192.168.1.251-254 (Standalone cameras)

### Scan for RTSP (Port 554)

```bash
for ip in $(seq 1 254); do
  timeout 0.5 bash -c "echo >/dev/tcp/192.168.1.$ip/554" 2>/dev/null && echo "192.168.1.$ip:554"
done
```

**Result:** Only `192.168.1.3:554` (NVR) has RTSP open - cameras are behind NVR.

---

## Step 3: UNV Camera Detection Script

### Created Python Detection Tool

Location: `/home/smartice001/smartice/ASEOfSmartICE/unv-camera-detection/detect_cameras.py`

**Features:**
- ONVIF WS-Discovery protocol
- UNV LAPI REST API queries
- ARP table scanning
- HTTP/HTTPS server identification
- Parallel scanning with ThreadPoolExecutor

**Usage:**
```bash
python3 detect_cameras.py                      # Auto-detect network
python3 detect_cameras.py -n 192.168.1.0/24    # Specific network
python3 detect_cameras.py -u admin -p 123456   # Custom credentials
python3 detect_cameras.py -o cameras.json      # Export to JSON
```

---

## Step 4: NVR Connection

### NVR Details

- **IP Address:** 192.168.1.3
- **Username:** admin
- **Password:** 123456
- **Web Interface:** http://192.168.1.3 or https://192.168.1.3

### Key Finding

The 30 cameras are connected to the **NVR's internal PoE ports**, not directly accessible on the network. The NVR acts as a gateway/proxy for all camera streams.

---

## Step 5: RTSP Stream Discovery

### Test RTSP Channels with FFprobe

```bash
for ch in $(seq 1 36); do
  if timeout 3 ffprobe -v quiet "rtsp://admin:123456@192.168.1.3:554/unicast/c${ch}/s0/live"; then
    echo "Channel $ch: Online"
  fi
done
```

### Result: 30 Cameras Online

All channels 1-30 responded successfully.

---

## Camera RTSP URLs

### URL Format

```
rtsp://admin:123456@192.168.1.3:554/unicast/c{CHANNEL}/s0/live
```

- `s0` = Main stream (high quality)
- `s1` = Sub stream (lower quality, less bandwidth)

### Complete Camera List

| Channel | RTSP URL |
|---------|----------|
| 1 | `rtsp://admin:123456@192.168.1.3:554/unicast/c1/s0/live` |
| 2 | `rtsp://admin:123456@192.168.1.3:554/unicast/c2/s0/live` |
| 3 | `rtsp://admin:123456@192.168.1.3:554/unicast/c3/s0/live` |
| 4 | `rtsp://admin:123456@192.168.1.3:554/unicast/c4/s0/live` |
| 5 | `rtsp://admin:123456@192.168.1.3:554/unicast/c5/s0/live` |
| 6 | `rtsp://admin:123456@192.168.1.3:554/unicast/c6/s0/live` |
| 7 | `rtsp://admin:123456@192.168.1.3:554/unicast/c7/s0/live` |
| 8 | `rtsp://admin:123456@192.168.1.3:554/unicast/c8/s0/live` |
| 9 | `rtsp://admin:123456@192.168.1.3:554/unicast/c9/s0/live` |
| 10 | `rtsp://admin:123456@192.168.1.3:554/unicast/c10/s0/live` |
| 11 | `rtsp://admin:123456@192.168.1.3:554/unicast/c11/s0/live` |
| 12 | `rtsp://admin:123456@192.168.1.3:554/unicast/c12/s0/live` |
| 13 | `rtsp://admin:123456@192.168.1.3:554/unicast/c13/s0/live` |
| 14 | `rtsp://admin:123456@192.168.1.3:554/unicast/c14/s0/live` |
| 15 | `rtsp://admin:123456@192.168.1.3:554/unicast/c15/s0/live` |
| 16 | `rtsp://admin:123456@192.168.1.3:554/unicast/c16/s0/live` |
| 17 | `rtsp://admin:123456@192.168.1.3:554/unicast/c17/s0/live` |
| 18 | `rtsp://admin:123456@192.168.1.3:554/unicast/c18/s0/live` |
| 19 | `rtsp://admin:123456@192.168.1.3:554/unicast/c19/s0/live` |
| 20 | `rtsp://admin:123456@192.168.1.3:554/unicast/c20/s0/live` |
| 21 | `rtsp://admin:123456@192.168.1.3:554/unicast/c21/s0/live` |
| 22 | `rtsp://admin:123456@192.168.1.3:554/unicast/c22/s0/live` |
| 23 | `rtsp://admin:123456@192.168.1.3:554/unicast/c23/s0/live` |
| 24 | `rtsp://admin:123456@192.168.1.3:554/unicast/c24/s0/live` |
| 25 | `rtsp://admin:123456@192.168.1.3:554/unicast/c25/s0/live` |
| 26 | `rtsp://admin:123456@192.168.1.3:554/unicast/c26/s0/live` |
| 27 | `rtsp://admin:123456@192.168.1.3:554/unicast/c27/s0/live` |
| 28 | `rtsp://admin:123456@192.168.1.3:554/unicast/c28/s0/live` |
| 29 | `rtsp://admin:123456@192.168.1.3:554/unicast/c29/s0/live` |
| 30 | `rtsp://admin:123456@192.168.1.3:554/unicast/c30/s0/live` |

---

## Testing Camera Streams

### Using VLC

```bash
vlc rtsp://admin:123456@192.168.1.3:554/unicast/c1/s0/live
```

### Using FFplay

```bash
ffplay -rtsp_transport tcp rtsp://admin:123456@192.168.1.3:554/unicast/c1/s0/live
```

### Using Python/OpenCV

```python
import cv2

cap = cv2.VideoCapture("rtsp://admin:123456@192.168.1.3:554/unicast/c1/s0/live")
while True:
    ret, frame = cap.read()
    if ret:
        cv2.imshow("Camera 1", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
cap.release()
```

---

## Tools and Software

### Installed Tools

| Tool | Purpose |
|------|---------|
| GitHub CLI (`gh`) | Repository management |
| ZoneMinder | Video Management System (VMS) |
| FFprobe/FFmpeg | RTSP stream testing |
| Python 3.12 | Detection scripts |

### ZoneMinder Setup

```bash
# Install
sudo apt install zoneminder

# Database setup
sudo mysql -e "CREATE DATABASE zm;"
sudo mysql -e "CREATE USER 'zmuser'@'localhost' IDENTIFIED BY 'zmpass';"
sudo mysql -e "GRANT ALL PRIVILEGES ON zm.* TO 'zmuser'@'localhost';"
sudo mysql zm < /usr/share/zoneminder/db/zm_create.sql

# Configure
sudo sed -i 's/ZM_DB_USER=.*/ZM_DB_USER=zmuser/' /etc/zm/zm.conf
sudo sed -i 's/ZM_DB_PASS=.*/ZM_DB_PASS=zmpass/' /etc/zm/zm.conf

# Enable Apache
sudo a2enconf zoneminder
sudo a2enmod rewrite cgi
sudo systemctl restart apache2 zoneminder
```

**Access:** http://localhost/zm

---

## Files Created

```
/home/smartice001/smartice/ASEOfSmartICE/unv-camera-detection/
├── detect_cameras.py      # Python camera detection script
├── requirements.txt       # Python dependencies
└── CAMERA_SETUP_GUIDE.md  # This documentation
```

---

## Summary

1. **Network Type:** Dedicated surveillance network with PoE switch
2. **NVR:** Uniview NVR at 192.168.1.3 (MAC: 88:26:3F:...)
3. **Cameras:** 30 cameras connected via NVR internal PoE ports
4. **Access Method:** RTSP streams through NVR proxy
5. **Credentials:** admin / 123456
6. **Stream URL Pattern:** `rtsp://admin:123456@192.168.1.3:554/unicast/c{1-30}/s0/live`

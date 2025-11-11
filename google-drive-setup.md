# Google Drive CLI Setup Guide

## Installation Status

✅ **MacBook M4**: rclone v1.71.2 installed
⏳ **Linux RTX 3060 machines**: Instructions below

---

## 1. Configure Google Drive on MacBook

Run the interactive configuration:

```bash
rclone config
```

### Configuration Steps:

1. Type `n` for "New remote"
2. Name: Enter `gdrive` (or any name you prefer)
3. Storage: Type `drive` (for Google Drive)
4. Client ID & Secret: Press Enter to skip (use defaults)
5. Scope: Type `1` for "Full access"
6. Root folder ID: Press Enter to skip
7. Service Account: Press Enter to skip
8. Advanced config: Type `n` for no
9. Auto config: Type `y` for yes (will open browser)
10. Login to your Google account and authorize
11. Shared Drive: Type `n` for no (unless you need it)
12. Confirm: Type `y` to save

---

## 2. Common Commands

### List files in Google Drive root:
```bash
rclone ls gdrive:
```

### Upload a file:
```bash
rclone copy /path/to/local/file.txt gdrive:/folder/
```

### Upload a directory:
```bash
rclone copy /path/to/local/folder gdrive:/remote/folder/
```

### Download a file:
```bash
rclone copy gdrive:/remote/file.txt /path/to/local/
```

### Sync (one-way, delete extra files):
```bash
rclone sync /path/to/local gdrive:/remote
```

### Check what would be transferred (dry run):
```bash
rclone copy /path/to/local gdrive:/remote --dry-run -v
```

---

## 3. Install on Linux RTX 3060 Machines

SSH into each Linux machine and run:

```bash
# Install rclone
curl https://rclone.org/install.sh | sudo bash

# Verify installation
rclone version

# Configure (same steps as MacBook, but use headless mode)
rclone config
```

For **headless Linux servers** (no GUI browser):
- When asked "Auto config?", type `n` for no
- It will give you a URL to open on your MacBook
- Copy the auth code back to the Linux terminal

---

## 4. Helper Script for Train-Model Data Upload

A helper script has been created: `train-model/upload_to_gdrive.sh`

Usage:
```bash
cd train-model
./upload_to_gdrive.sh model_v3/dataset/train/
```

---

## 5. Background Sync (Optional)

To continuously sync a folder in the background:

```bash
rclone mount gdrive:/ ~/gdrive --daemon
```

Or use systemd on Linux for automatic syncing.

---

## Useful Options

- `--progress`: Show transfer progress
- `--dry-run`: Test without making changes
- `-v`: Verbose output
- `--transfers 4`: Parallel transfers (default 4)
- `--exclude "*.tmp"`: Exclude patterns
- `--include "*.jpg"`: Include only specific files

---

## Examples for Your Use Case

### Upload captured screenshots from Linux to Google Drive:
```bash
rclone copy /path/to/captured_images/ gdrive:/SmartICE/raw_images/ --progress
```

### Download training dataset to MacBook:
```bash
rclone copy gdrive:/SmartICE/raw_images/ ~/Desktop/Smartice/ASEOfSmartICE/train-model/model_v3/raw_images/ --progress
```

### Backup models to Google Drive:
```bash
rclone copy train-model/model_v3/models/ gdrive:/SmartICE/models/model_v3/ --progress
```

---

## Configuration File Location

- **MacBook**: `~/.config/rclone/rclone.conf`
- **Linux**: `~/.config/rclone/rclone.conf`

You can copy this config file to other machines to avoid re-authentication.

---

## Troubleshooting

### Error: "Failed to configure token"
- Make sure you're logged into the correct Google account
- Try running `rclone config reconnect gdrive:` to re-authenticate

### Slow transfers
- Increase parallel transfers: `--transfers 8`
- Use `--fast-list` for large directories

### Rate limit errors
- Google Drive has API limits
- Add `--tpslimit 10` to slow down requests

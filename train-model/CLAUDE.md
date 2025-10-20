# Train Model Directory

## Overview
This directory contains multiple versions of AI models for restaurant surveillance and different utilities for data collection.

## Directory Structure

### Model Versions
Each model version has its own folder with a dedicated CLAUDE.md explaining its purpose and usage.

- **`model_v1/`** - First employee/customer classifier (completed)
- **`model_v2/`** - Clean template ready for next training iteration
- **`model_v3/`** - Future: Activity recognition (planned)
- **`model_v4/`** - Future: Behavioral analysis (planned)

### Data Collection
- **`linux_rtx_screenshot_capture/`** - Automated screenshot capture system for RTX 3060 machines in restaurants

## Quick Navigation

| Folder | Purpose | Status |
|--------|---------|--------|
| `model_v1/` | Employee/Customer Classifier | ✅ Trained |
| `model_v2/` | Next Version Template | 🔄 Ready |
| `model_v3/` | Activity Recognition | 📋 Planned |
| `model_v4/` | Behavioral Analysis | 📋 Planned |
| `linux_rtx_screenshot_capture/` | Screenshot Capture | ✅ Active |

## How to Use

1. **For Training**: Go to the appropriate model version folder and follow its CLAUDE.md
2. **For Data Collection**: Check `linux_rtx_screenshot_capture/CLAUDE.md` for capture system setup
3. **For New Models**: Copy `model_v2/` as a clean starting template

## Model Evolution

```
V1: Person Detection → Employee/Customer Classification
V2: Improved Classification (pending)
V3: Activity Recognition (planned)
V4: Advanced Analytics (future)
```

Each version builds on learnings from the previous one. Check individual CLAUDE.md files for specific details.
# Features Directory

## Purpose

Lab environment for implementing single-purpose detection applications. Each feature explores one specific use case: "How can we use validated models to solve a restaurant problem?"

**Not production-ready** - These are building blocks that get integrated into `production/`.

---

## Current Features

### table-state-detection
Monitor restaurant tables to track customer occupancy and service interactions.

**States**: IDLE → OCCUPIED → SERVING → CLEANING

**Use Cases**:
- Measure time from seating to first order
- Track service response times
- Optimize table turnover

### region-state-detection
Monitor service zones to ensure staff coverage.

**States**: STAFFED (在岗) vs UNSTAFFED (脱岗)

**Use Cases**:
- Alert when zones unattended >5 seconds
- Staff allocation optimization

---

## Standard Structure

```
feature-name/
├── logic.md              # Algorithm documentation
├── feature-name.py       # Detection script
├── models/               # Model files (YOLOv8m, classifiers)
├── videos/               # Test videos for development
├── images/               # Test images for validation
└── results/              # Output videos and analysis results (created automatically)
    └── feature-name_videoname.mp4  # Annotated output videos
```

**Note**: The `results/` folder stores all processed outputs including annotated videos, detection logs, and performance metrics. This folder is automatically created when running detection scripts and should not be committed to version control.

---

**See root CLAUDE.md for full workflow and deployment pipeline.**

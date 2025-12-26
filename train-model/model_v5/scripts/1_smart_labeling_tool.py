#!/usr/bin/env python3
"""
Smart Labeling Tool for Staff/Customer Detection - V5
Version: 1.0.0

References images from model_v4/filtered_images_with_people
Does NOT modify v4 data - all labels saved to v5/labeled_staff_customer/

Features:
- Pre-detects all persons using YOLO11m
- Click to classify: Staff (green) / Customer (red)
- Draw new boxes for missed detections
- 2-class output: staff (0), customer (1)
- Fast labeling workflow with keyboard shortcuts

Created: 2025-12-26
"""

import cv2
import numpy as np
from ultralytics import YOLO
from flask import Flask, render_template_string, jsonify, request, send_file
import sqlite3
import os
from pathlib import Path
import json
from datetime import datetime

# =============================================================================
# Configuration
# =============================================================================

SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_DIR = SCRIPT_DIR.parent

# V4 images directory (READ ONLY - do not modify)
V4_DIR = PROJECT_DIR.parent / "model_v4"
INPUT_DIR = V4_DIR / "filtered_images_with_people"

# V5 output directory (all labels saved here)
OUTPUT_DIR = PROJECT_DIR / "labeled_staff_customer"
DB_PATH = OUTPUT_DIR / "labels.db"

# YOLO11m for person detection
DETECTOR_MODEL = "yolo11m.pt"
PERSON_CONF = 0.35  # Lower threshold to catch more people
PERSON_CLASS = 0    # COCO class for person

# Server
SERVER_PORT = 5005

# =============================================================================
# Flask App
# =============================================================================

app = Flask(__name__)

# Global state
detector = None
current_images = []
current_index = 0
current_detections = []  # List of {bbox, class: 'staff'/'customer'/None}

def init_detector():
    """Initialize YOLO11m detector"""
    global detector
    print("Loading YOLO11m for person detection...")
    detector = YOLO(DETECTOR_MODEL)
    print("Detector loaded!")

def init_database():
    """Initialize SQLite database in V5 directory"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT UNIQUE NOT NULL,
            channel TEXT,
            labeled_at TIMESTAMP,
            skipped BOOLEAN DEFAULT FALSE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS boxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            x1 REAL NOT NULL,
            y1 REAL NOT NULL,
            x2 REAL NOT NULL,
            y2 REAL NOT NULL,
            class_name TEXT NOT NULL,
            confidence REAL,
            auto_detected BOOLEAN DEFAULT TRUE,
            FOREIGN KEY (image_id) REFERENCES images (id)
        )
    ''')

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

def load_images():
    """Load all images from V4 directory (read-only reference)"""
    global current_images, current_index

    if not INPUT_DIR.exists():
        print(f"ERROR: V4 images directory not found: {INPUT_DIR}")
        return

    current_images = []

    # Walk through all subdirectories
    for root, dirs, files in os.walk(INPUT_DIR):
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                full_path = Path(root) / f
                rel_path = full_path.relative_to(INPUT_DIR)
                current_images.append({
                    'path': str(full_path),
                    'filename': str(rel_path),
                    'channel': rel_path.parts[0] if len(rel_path.parts) > 1 else 'unknown'
                })

    # Sort by filename
    current_images.sort(key=lambda x: x['filename'])

    # Get labeled/skipped filenames
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT filename FROM images WHERE labeled_at IS NOT NULL OR skipped = TRUE")
    labeled = set(row[0] for row in cursor.fetchall())
    conn.close()

    # Find first unlabeled image index (don't remove labeled images!)
    current_index = 0
    for i, img in enumerate(current_images):
        if img['filename'] not in labeled:
            current_index = i
            break
    else:
        # All labeled
        current_index = len(current_images)

    labeled_count = len(labeled)
    total_count = len(current_images)
    remaining = total_count - labeled_count

    print(f"Total: {total_count} images, Labeled: {labeled_count}, Remaining: {remaining}")
    print(f"Starting at image {current_index + 1}")

def detect_persons(image_path):
    """Detect all persons in image using YOLO11m"""
    global detector

    results = detector(image_path, conf=PERSON_CONF, classes=[PERSON_CLASS], verbose=False)

    detections = []
    for r in results:
        if r.boxes is not None:
            for box in r.boxes:
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                conf = float(box.conf[0])
                detections.append({
                    'bbox': [int(x1), int(y1), int(x2), int(y2)],
                    'confidence': conf,
                    'class': None,  # To be assigned by user clicking
                    'auto_detected': True
                })

    return detections

# =============================================================================
# HTML Template - Enhanced UI
# =============================================================================

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>V5 Smart Labeling - Staff/Customer</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, sans-serif;
            background: #1a1a2e;
            color: #fff;
            height: 100vh;
            overflow: hidden;
        }
        .header {
            background: #16213e;
            padding: 12px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 3px solid #00ff88;
        }
        .header h1 { font-size: 18px; color: #00ff88; }
        .stats { display: flex; gap: 15px; font-size: 13px; }
        .stat {
            background: #0f3460;
            padding: 6px 12px;
            border-radius: 5px;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .stat.staff { border-left: 3px solid #00ff88; }
        .stat.customer { border-left: 3px solid #ff4444; }
        .stat.unlabeled { border-left: 3px solid #888; }

        .main {
            display: flex;
            height: calc(100vh - 60px);
        }

        .canvas-container {
            flex: 1;
            display: flex;
            justify-content: center;
            align-items: center;
            background: #0a0a0a;
            position: relative;
        }

        #canvas {
            max-width: 100%;
            max-height: 100%;
            cursor: pointer;
        }

        .sidebar {
            width: 300px;
            background: #16213e;
            padding: 15px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
        }

        .section { margin-bottom: 20px; }
        .section h3 {
            font-size: 12px;
            color: #888;
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .legend {
            display: flex;
            gap: 20px;
            margin-bottom: 10px;
        }
        .legend-item {
            display: flex;
            align-items: center;
            gap: 6px;
            font-size: 13px;
        }
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 3px;
        }
        .staff-color { background: #00ff88; }
        .customer-color { background: #ff4444; }
        .unlabeled-color { background: #888; border: 2px dashed #fff; }

        .detection-list {
            flex: 1;
            overflow-y: auto;
            max-height: 250px;
        }
        .detection-item {
            background: #0f3460;
            padding: 8px 10px;
            margin-bottom: 6px;
            border-radius: 5px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            border: 2px solid transparent;
            transition: all 0.15s;
        }
        .detection-item:hover {
            border-color: #00ff88;
            transform: translateX(3px);
        }
        .detection-item.staff { border-left: 4px solid #00ff88; background: #0f3460; }
        .detection-item.customer { border-left: 4px solid #ff4444; background: #0f3460; }
        .detection-item.unlabeled { border-left: 4px solid #888; opacity: 0.7; }

        .btn-group {
            display: flex;
            gap: 4px;
        }
        .btn {
            padding: 4px 8px;
            border: none;
            border-radius: 3px;
            cursor: pointer;
            font-size: 11px;
            font-weight: 600;
            transition: transform 0.1s;
        }
        .btn:hover { transform: scale(1.1); }
        .btn-staff { background: #00ff88; color: #000; }
        .btn-customer { background: #ff4444; color: #fff; }
        .btn-delete { background: #333; color: #fff; }

        .actions {
            display: flex;
            flex-direction: column;
            gap: 8px;
        }
        .action-btn {
            padding: 10px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s;
        }
        .action-btn:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
        .action-btn.primary { background: #00ff88; color: #000; }
        .action-btn.secondary { background: #0f3460; color: #fff; }
        .action-btn.skip { background: #ff8800; color: #000; }
        .action-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }

        .shortcuts {
            font-size: 11px;
            color: #666;
        }
        .shortcut {
            display: flex;
            justify-content: space-between;
            padding: 4px 0;
            border-bottom: 1px solid #333;
        }
        .key {
            background: #333;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
            font-size: 10px;
        }

        .mode-indicator {
            position: fixed;
            bottom: 20px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(255,255,0,0.9);
            color: #000;
            padding: 10px 25px;
            border-radius: 5px;
            font-size: 14px;
            font-weight: bold;
            display: none;
            z-index: 100;
        }
        .mode-indicator.active { display: block; }

        .toast {
            position: fixed;
            top: 80px;
            left: 50%;
            transform: translateX(-50%);
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 16px;
            font-weight: bold;
            z-index: 200;
            opacity: 0;
            transition: opacity 0.3s;
            pointer-events: none;
        }
        .toast.show { opacity: 1; }
        .toast.save { background: #00ff88; color: #000; }
        .toast.skip { background: #ff8800; color: #000; }
        .toast.prev { background: #0f3460; color: #fff; }

        .filename {
            font-size: 11px;
            color: #555;
            word-break: break-all;
            margin-top: 10px;
            padding: 8px;
            background: #0a0a0a;
            border-radius: 3px;
        }

        .progress-bar {
            height: 4px;
            background: #333;
            border-radius: 2px;
            overflow: hidden;
            margin-bottom: 15px;
        }
        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #00ff88, #00cc66);
            transition: width 0.3s;
        }

        .tip {
            background: #0f3460;
            padding: 10px;
            border-radius: 5px;
            font-size: 12px;
            color: #aaa;
            margin-bottom: 15px;
            border-left: 3px solid #00ff88;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🏷️ V5 Staff/Customer Labeling</h1>
        <div class="stats">
            <div class="stat">Progress: <strong id="current-index">0</strong> / <strong id="total-images">0</strong></div>
            <div class="stat staff">Staff: <strong id="staff-count">0</strong></div>
            <div class="stat customer">Customer: <strong id="customer-count">0</strong></div>
            <div class="stat unlabeled">?: <strong id="unlabeled-count">0</strong></div>
        </div>
    </div>

    <div class="main">
        <div class="canvas-container">
            <canvas id="canvas"></canvas>
        </div>

        <div class="sidebar">
            <div class="progress-bar">
                <div class="progress-fill" id="progress-fill" style="width: 0%"></div>
            </div>

            <div class="tip">
                💡 <strong>Click boxes</strong> to toggle Staff↔Customer. All must be labeled to save.
            </div>

            <div class="section">
                <h3>Legend</h3>
                <div class="legend">
                    <div class="legend-item">
                        <div class="legend-color staff-color"></div>
                        <span>Staff</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color customer-color"></div>
                        <span>Customer</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-color unlabeled-color"></div>
                        <span>Unlabeled</span>
                    </div>
                </div>
            </div>

            <div class="section" style="flex: 1;">
                <h3>Detections (<span id="detection-count">0</span>)</h3>
                <div class="detection-list" id="detection-list"></div>
            </div>

            <div class="section">
                <h3>Quick Actions</h3>
                <div class="actions">
                    <button class="action-btn primary" id="save-btn" onclick="saveAndNext()">
                        ✓ Save & Next (S / Enter)
                    </button>
                    <button class="action-btn skip" onclick="skipImage()">
                        ⏭ Skip (D)
                    </button>
                    <div style="display: flex; gap: 8px;">
                        <button class="action-btn secondary" style="flex:1" onclick="setAllStaff()">
                            All Staff (1)
                        </button>
                        <button class="action-btn secondary" style="flex:1" onclick="setAllCustomer()">
                            All Customer (2)
                        </button>
                    </div>
                    <button class="action-btn secondary" onclick="toggleDrawMode()">
                        ✏️ Draw New Box (F)
                    </button>
                    <button class="action-btn secondary" onclick="prevImage()">
                        ← Previous (A / ←)
                    </button>
                </div>
            </div>

            <div class="section">
                <h3>Shortcuts</h3>
                <div class="shortcuts">
                    <div class="shortcut"><span>Previous</span><span class="key">A / ←</span></div>
                    <div class="shortcut"><span>Save & Next</span><span class="key">S / Enter</span></div>
                    <div class="shortcut"><span>Skip</span><span class="key">D</span></div>
                    <div class="shortcut"><span>Draw Box</span><span class="key">F</span></div>
                    <div class="shortcut"><span>All Staff</span><span class="key">1</span></div>
                    <div class="shortcut"><span>All Customer</span><span class="key">2</span></div>
                </div>
            </div>

            <div class="filename" id="filename"></div>
        </div>
    </div>

    <div class="mode-indicator" id="mode-indicator">
        ✏️ DRAW MODE: Click & drag to draw box (ESC to cancel)
    </div>

    <div class="toast" id="toast"></div>

    <script>
        let canvas, ctx;
        let currentImage = null;
        let detections = [];
        let drawMode = false;
        let drawing = false;
        let startX, startY;
        let scale = 1;
        let totalImages = 0;
        let currentIdx = 0;

        function showToast(message, type) {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast show ' + type;
            setTimeout(() => { toast.classList.remove('show'); }, 800);
        }

        // Initialize
        window.onload = function() {
            canvas = document.getElementById('canvas');
            ctx = canvas.getContext('2d');

            canvas.addEventListener('click', onCanvasClick);
            canvas.addEventListener('mousedown', onMouseDown);
            canvas.addEventListener('mousemove', onMouseMove);
            canvas.addEventListener('mouseup', onMouseUp);

            document.addEventListener('keydown', onKeyDown);

            loadImage();
        };

        function loadImage() {
            fetch('/api/current')
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                        return;
                    }

                    currentIdx = data.index;
                    totalImages = data.total;

                    document.getElementById('current-index').textContent = data.index + 1;
                    document.getElementById('total-images').textContent = data.total;
                    document.getElementById('filename').textContent = '📁 ' + data.filename;

                    // Update progress bar
                    const progress = ((data.index + 1) / data.total * 100).toFixed(1);
                    document.getElementById('progress-fill').style.width = progress + '%';

                    detections = data.detections;

                    // Load image
                    currentImage = new Image();
                    currentImage.onload = function() {
                        resizeCanvas();
                        render();
                        updateDetectionList();
                        updateSaveButton();
                    };
                    currentImage.src = '/api/image/' + data.index;
                });
        }

        function resizeCanvas() {
            const container = canvas.parentElement;
            const maxW = container.clientWidth - 40;
            const maxH = container.clientHeight - 40;

            const imgRatio = currentImage.width / currentImage.height;
            const containerRatio = maxW / maxH;

            if (imgRatio > containerRatio) {
                canvas.width = maxW;
                canvas.height = maxW / imgRatio;
            } else {
                canvas.height = maxH;
                canvas.width = maxH * imgRatio;
            }

            scale = canvas.width / currentImage.width;
        }

        function render() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(currentImage, 0, 0, canvas.width, canvas.height);

            let staffCount = 0, customerCount = 0, unlabeledCount = 0;

            // Draw detection boxes
            detections.forEach((det, i) => {
                const [x1, y1, x2, y2] = det.bbox.map(v => v * scale);

                let color, label;
                if (det.class === 'staff') {
                    color = '#00ff88';
                    label = 'STAFF';
                    staffCount++;
                } else if (det.class === 'customer') {
                    color = '#ff4444';
                    label = 'CUSTOMER';
                    customerCount++;
                } else {
                    color = '#888888';
                    label = '? CLICK ME';
                    unlabeledCount++;
                    ctx.setLineDash([8, 4]);
                }

                // Draw box
                ctx.strokeStyle = color;
                ctx.lineWidth = 3;
                ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
                ctx.setLineDash([]);

                // Semi-transparent fill for unlabeled
                if (!det.class) {
                    ctx.fillStyle = 'rgba(255,255,0,0.1)';
                    ctx.fillRect(x1, y1, x2 - x1, y2 - y1);
                }

                // Label background
                ctx.fillStyle = color;
                const text = `${i + 1}. ${label}`;
                ctx.font = 'bold 13px sans-serif';
                const textWidth = ctx.measureText(text).width + 10;
                ctx.fillRect(x1, y1 - 22, textWidth, 20);

                // Label text
                ctx.fillStyle = det.class === 'staff' ? '#000' : '#fff';
                ctx.fillText(text, x1 + 5, y1 - 6);
            });

            document.getElementById('staff-count').textContent = staffCount;
            document.getElementById('customer-count').textContent = customerCount;
            document.getElementById('unlabeled-count').textContent = unlabeledCount;
            document.getElementById('detection-count').textContent = detections.length;
        }

        function updateDetectionList() {
            const list = document.getElementById('detection-list');
            list.innerHTML = '';

            detections.forEach((det, i) => {
                const div = document.createElement('div');
                div.className = 'detection-item ' + (det.class || 'unlabeled');
                const conf = det.confidence ? `${(det.confidence * 100).toFixed(0)}%` : 'manual';
                div.innerHTML = `
                    <span>#${i + 1} - ${det.class || 'Unlabeled'} (${conf})</span>
                    <div class="btn-group">
                        <button class="btn btn-staff" onclick="event.stopPropagation(); setClass(${i}, 'staff')">S</button>
                        <button class="btn btn-customer" onclick="event.stopPropagation(); setClass(${i}, 'customer')">C</button>
                        <button class="btn btn-delete" onclick="event.stopPropagation(); deleteDetection(${i})">×</button>
                    </div>
                `;
                div.onclick = () => toggleClass(i);
                list.appendChild(div);
            });
        }

        function updateSaveButton() {
            const btn = document.getElementById('save-btn');
            const labeled = detections.filter(d => d.class !== null).length;
            const total = detections.length;
            if (total === 0) {
                btn.textContent = '✓ Save as Background (S)';
            } else {
                btn.textContent = `✓ Save ${labeled}/${total} boxes (S)`;
            }
            btn.disabled = false;
        }

        function onCanvasClick(e) {
            if (drawMode) return;

            const rect = canvas.getBoundingClientRect();
            const x = (e.clientX - rect.left) / scale;
            const y = (e.clientY - rect.top) / scale;

            // Find clicked detection (reverse order for top-most)
            for (let i = detections.length - 1; i >= 0; i--) {
                const [x1, y1, x2, y2] = detections[i].bbox;
                if (x >= x1 && x <= x2 && y >= y1 && y <= y2) {
                    toggleClass(i);
                    return;
                }
            }
        }

        function toggleClass(i) {
            // Cycle: null -> staff -> customer -> staff
            if (detections[i].class === null) {
                detections[i].class = 'staff';
            } else if (detections[i].class === 'staff') {
                detections[i].class = 'customer';
            } else {
                detections[i].class = 'staff';
            }
            render();
            updateDetectionList();
            updateSaveButton();
        }

        function setClass(i, cls) {
            detections[i].class = cls;
            render();
            updateDetectionList();
            updateSaveButton();
        }

        function deleteDetection(i) {
            detections.splice(i, 1);
            render();
            updateDetectionList();
            updateSaveButton();
        }

        function setAllStaff() {
            detections.forEach(d => d.class = 'staff');
            render();
            updateDetectionList();
            updateSaveButton();
        }

        function setAllCustomer() {
            detections.forEach(d => d.class = 'customer');
            render();
            updateDetectionList();
            updateSaveButton();
        }

        function toggleDrawMode() {
            drawMode = !drawMode;
            document.getElementById('mode-indicator').classList.toggle('active', drawMode);
            canvas.style.cursor = drawMode ? 'crosshair' : 'pointer';
        }

        function onMouseDown(e) {
            if (!drawMode) return;
            drawing = true;
            const rect = canvas.getBoundingClientRect();
            startX = (e.clientX - rect.left) / scale;
            startY = (e.clientY - rect.top) / scale;
        }

        function onMouseMove(e) {
            if (!drawing) return;
            const rect = canvas.getBoundingClientRect();
            const x = (e.clientX - rect.left) / scale;
            const y = (e.clientY - rect.top) / scale;

            render();

            // Draw temp box
            ctx.strokeStyle = '#ffff00';
            ctx.lineWidth = 2;
            ctx.setLineDash([5, 5]);
            ctx.strokeRect(startX * scale, startY * scale, (x - startX) * scale, (y - startY) * scale);
            ctx.setLineDash([]);
        }

        function onMouseUp(e) {
            if (!drawing) return;
            drawing = false;

            const rect = canvas.getBoundingClientRect();
            const endX = (e.clientX - rect.left) / scale;
            const endY = (e.clientY - rect.top) / scale;

            // Add new detection if box is big enough
            const x1 = Math.min(startX, endX);
            const y1 = Math.min(startY, endY);
            const x2 = Math.max(startX, endX);
            const y2 = Math.max(startY, endY);

            if (x2 - x1 > 20 && y2 - y1 > 20) {
                detections.push({
                    bbox: [Math.round(x1), Math.round(y1), Math.round(x2), Math.round(y2)],
                    confidence: 1.0,
                    class: 'staff',  // Default to staff for manually drawn
                    auto_detected: false
                });
                render();
                updateDetectionList();
                updateSaveButton();
            }

            drawMode = false;
            document.getElementById('mode-indicator').classList.remove('active');
            canvas.style.cursor = 'pointer';
        }

        function saveAndNext() {
            // Save only labeled boxes (unlabeled ones are ignored)
            fetch('/api/save', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({detections: detections.filter(d => d.class !== null)})
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    fetch('/api/next', {method: 'POST'})
                        .then(() => loadImage());
                }
            });
        }

        function skipImage() {
            fetch('/api/skip', {method: 'POST'})
                .then(() => {
                    fetch('/api/next', {method: 'POST'})
                        .then(() => loadImage());
                });
        }

        function prevImage() {
            fetch('/api/prev', {method: 'POST'})
                .then(() => loadImage());
        }

        function onKeyDown(e) {
            if (e.key === 'Enter' || e.key === 's' || e.key === 'S') {
                e.preventDefault();
                if (e.key === 's' || e.key === 'S') {
                    showToast('💾 Saving...', 'save');
                }
                saveAndNext();
            } else if (e.key === 'd' || e.key === 'D') {
                e.preventDefault();
                showToast('⏭ Skipping...', 'skip');
                skipImage();
            } else if (e.key === 'a' || e.key === 'A' || e.key === 'ArrowLeft') {
                e.preventDefault();
                showToast('← Previous', 'prev');
                prevImage();
            } else if (e.key === '1') {
                e.preventDefault();
                setAllStaff();
            } else if (e.key === '2') {
                e.preventDefault();
                setAllCustomer();
            } else if (e.key === 'f' || e.key === 'F') {
                e.preventDefault();
                toggleDrawMode();
            } else if (e.key === 'Escape') {
                drawMode = false;
                drawing = false;
                document.getElementById('mode-indicator').classList.remove('active');
                canvas.style.cursor = 'pointer';
                render();
            } else if (e.key === 'Backspace') {
                e.preventDefault();
                if (detections.length > 0) {
                    detections.pop();
                    render();
                    updateDetectionList();
                    updateSaveButton();
                }
            }
        }
    </script>
</body>
</html>
'''

# =============================================================================
# API Routes
# =============================================================================

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/current')
def api_current():
    global current_images, current_index, current_detections

    if not current_images:
        return jsonify({'error': 'No images to label. Check V4 directory.'})

    if current_index >= len(current_images):
        return jsonify({'error': '🎉 All images labeled! Run Step 2 to prepare dataset.'})

    img_info = current_images[current_index]

    # Check if already labeled - load from database
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT id, labeled_at FROM images WHERE filename = ?", (img_info['filename'],))
    row = cursor.fetchone()

    if row and row[1]:  # Has labeled_at timestamp
        image_id = row[0]
        cursor.execute("""
            SELECT x1, y1, x2, y2, class_name, confidence, auto_detected
            FROM boxes WHERE image_id = ?
        """, (image_id,))
        boxes = cursor.fetchall()
        conn.close()

        current_detections = [{
            'bbox': [int(b[0]), int(b[1]), int(b[2]), int(b[3])],
            'confidence': b[5] or 1.0,
            'class': b[4],
            'auto_detected': bool(b[6])
        } for b in boxes]
    else:
        conn.close()
        # Not labeled yet - detect persons
        current_detections = detect_persons(img_info['path'])

    return jsonify({
        'index': current_index,
        'total': len(current_images),
        'filename': img_info['filename'],
        'channel': img_info['channel'],
        'detections': current_detections
    })

@app.route('/api/image/<int:idx>')
def api_image(idx):
    if idx < 0 or idx >= len(current_images):
        return 'Not found', 404
    return send_file(current_images[idx]['path'])

@app.route('/api/save', methods=['POST'])
def api_save():
    global current_images, current_index

    data = request.json
    detections = data.get('detections', [])

    img_info = current_images[current_index]

    # Save to V5 database (not V4!)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    # Insert or update image record
    cursor.execute('''
        INSERT OR REPLACE INTO images (filename, channel, labeled_at, skipped)
        VALUES (?, ?, ?, FALSE)
    ''', (img_info['filename'], img_info['channel'], datetime.now().isoformat()))

    image_id = cursor.lastrowid or cursor.execute(
        "SELECT id FROM images WHERE filename = ?", (img_info['filename'],)
    ).fetchone()[0]

    # Delete old boxes
    cursor.execute("DELETE FROM boxes WHERE image_id = ?", (image_id,))

    # Insert new boxes (only labeled ones)
    for det in detections:
        if det.get('class'):
            x1, y1, x2, y2 = det['bbox']
            cursor.execute('''
                INSERT INTO boxes (image_id, x1, y1, x2, y2, class_name, confidence, auto_detected)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (image_id, x1, y1, x2, y2, det['class'], det.get('confidence', 1.0), det.get('auto_detected', True)))

    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/skip', methods=['POST'])
def api_skip():
    global current_images, current_index

    img_info = current_images[current_index]

    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO images (filename, channel, skipped)
        VALUES (?, ?, TRUE)
    ''', (img_info['filename'], img_info['channel']))
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/next', methods=['POST'])
def api_next():
    global current_index
    if current_index < len(current_images) - 1:
        current_index += 1
    return jsonify({'index': current_index})

@app.route('/api/prev', methods=['POST'])
def api_prev():
    global current_index
    if current_index > 0:
        current_index -= 1
    return jsonify({'index': current_index})

@app.route('/api/stats')
def api_stats():
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM images WHERE labeled_at IS NOT NULL")
    labeled = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM images WHERE skipped = TRUE")
    skipped = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM boxes WHERE class_name = 'staff'")
    staff_boxes = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM boxes WHERE class_name = 'customer'")
    customer_boxes = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        'labeled_images': labeled,
        'skipped_images': skipped,
        'staff_boxes': staff_boxes,
        'customer_boxes': customer_boxes,
        'total_images': len(current_images) + labeled + skipped
    })

# =============================================================================
# Main
# =============================================================================

def main():
    print("\n" + "=" * 60)
    print("🏷️  V5 Smart Labeling Tool - Staff/Customer Detection")
    print("=" * 60)
    print(f"\n📂 Reading images from V4: {INPUT_DIR}")
    print(f"💾 Saving labels to V5: {DB_PATH}")

    # Initialize
    init_database()
    init_detector()
    load_images()

    if not current_images:
        print("\n❌ No images found to label!")
        print(f"   Please ensure V4 images exist at:")
        print(f"   {INPUT_DIR}")
        return

    print(f"\n📊 Found {len(current_images)} images to label")
    print(f"\n🌐 Starting server at http://localhost:{SERVER_PORT}")
    print("\n📌 Workflow:")
    print("   1. Click boxes to toggle Staff ↔ Customer")
    print("   2. Press 'D' to draw missed detections")
    print("   3. Press Enter to save and continue")
    print("   4. Press 'S' to skip (no people)")
    print("\n" + "=" * 60)

    app.run(host='0.0.0.0', port=SERVER_PORT, debug=False)

if __name__ == '__main__':
    main()

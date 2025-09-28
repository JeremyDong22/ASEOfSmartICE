#!/usr/bin/env python3
# Version: 1.0
# Manual image labeling tool for waiter vs customer classification
# Simple web interface for fast labeling

import cv2
import os
from flask import Flask, render_template_string, jsonify, request
import json
from pathlib import Path
import shutil

app = Flask(__name__)

# Paths
INPUT_DIR = "../extracted-persons/training_video_20250927_202033"
OUTPUT_DIR = "../labeled-persons"

# Global state
current_index = 0
images = []
labels = {}  # {filename: 'waiter' or 'customer'}

def setup():
    """Initialize and load images"""
    global images

    # Create output directories
    os.makedirs(f"{OUTPUT_DIR}/waiters", exist_ok=True)
    os.makedirs(f"{OUTPUT_DIR}/customers", exist_ok=True)

    # Load existing labels if any
    labels_file = f"{OUTPUT_DIR}/labels.json"
    if os.path.exists(labels_file):
        with open(labels_file, 'r') as f:
            labels.update(json.load(f))

    # Get all images
    images = sorted([f for f in os.listdir(INPUT_DIR) if f.endswith(('.jpg', '.png'))])
    print(f"📷 Found {len(images)} images to label")
    print(f"✅ Already labeled: {len(labels)} images")

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Image Labeling Tool</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            background-color: #2c3e50;
            color: white;
            margin: 0;
            padding: 20px;
            text-align: center;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        h1 {
            color: #ecf0f1;
        }
        .image-container {
            background: #34495e;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }
        #current-image {
            max-width: 100%;
            max-height: 600px;
            border: 2px solid #16a085;
            border-radius: 5px;
        }
        .controls {
            margin: 20px 0;
        }
        button {
            font-size: 20px;
            padding: 15px 30px;
            margin: 0 10px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            transition: background-color 0.3s;
        }
        .btn-waiter {
            background-color: #3498db;
            color: white;
        }
        .btn-waiter:hover {
            background-color: #2980b9;
        }
        .btn-customer {
            background-color: #e74c3c;
            color: white;
        }
        .btn-customer:hover {
            background-color: #c0392b;
        }
        .btn-skip {
            background-color: #95a5a6;
            color: white;
        }
        .btn-skip:hover {
            background-color: #7f8c8d;
        }
        .btn-back {
            background-color: #f39c12;
            color: white;
        }
        .btn-back:hover {
            background-color: #e67e22;
        }
        .progress {
            background: #34495e;
            border-radius: 10px;
            padding: 20px;
            margin: 20px 0;
        }
        .progress-bar {
            background: #27ae60;
            height: 30px;
            border-radius: 5px;
            transition: width 0.3s;
        }
        .stats {
            display: flex;
            justify-content: space-around;
            margin: 20px 0;
        }
        .stat-box {
            background: #34495e;
            padding: 15px;
            border-radius: 5px;
            min-width: 150px;
        }
        .keyboard-hints {
            background: #34495e;
            padding: 15px;
            border-radius: 5px;
            margin-top: 20px;
            font-size: 14px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>👤 Person Classification Tool</h1>

        <div class="progress">
            <div>Progress: <span id="current">0</span> / <span id="total">0</span></div>
            <div style="background: #2c3e50; margin-top: 10px;">
                <div class="progress-bar" id="progress-bar"></div>
            </div>
        </div>

        <div class="stats">
            <div class="stat-box">
                <h3>👔 Waiters</h3>
                <div id="waiter-count">0</div>
            </div>
            <div class="stat-box">
                <h3>🧑 Customers</h3>
                <div id="customer-count">0</div>
            </div>
            <div class="stat-box">
                <h3>📝 Total Labeled</h3>
                <div id="labeled-count">0</div>
            </div>
        </div>

        <div class="image-container">
            <img id="current-image" src="" alt="Current Image">
            <div id="image-name" style="margin-top: 10px; font-size: 12px; color: #95a5a6;"></div>
        </div>

        <div style="background: #34495e; padding: 20px; border-radius: 10px; margin: 20px 0;">
            <h2>Current Selection: <span id="current-label" style="color: #e74c3c;">🧑 Customer</span></h2>
            <p style="color: #95a5a6;">Press SPACE to toggle between Waiter/Customer</p>
        </div>

        <div class="controls">
            <button class="btn-back" onclick="previousImage()">⬅️ Previous (←)</button>
            <button class="btn-waiter" onclick="setLabel('waiter')">👔 Waiter</button>
            <button class="btn-customer" onclick="setLabel('customer')">🧑 Customer</button>
            <button style="background-color: #27ae60; color: white; padding: 15px 40px;" onclick="saveAndNext()">
                ✅ Save & Next (Enter)
            </button>
        </div>

        <div class="keyboard-hints">
            ⌨️ Keyboard Shortcuts: Space = Toggle | Enter = Save & Next | ← = Previous
        </div>
    </div>

    <script>
        let currentIndex = 0;
        let total = 0;

        let currentLabel = 'customer';  // Default is customer

        // Update UI to show current selection
        function updateLabelButtons() {
            const waiterBtn = document.querySelector('.btn-waiter');
            const customerBtn = document.querySelector('.btn-customer');

            if (currentLabel === 'waiter') {
                waiterBtn.style.opacity = '1';
                waiterBtn.style.boxShadow = '0 0 20px rgba(52, 152, 219, 0.8)';
                customerBtn.style.opacity = '0.5';
                customerBtn.style.boxShadow = 'none';
            } else {
                customerBtn.style.opacity = '1';
                customerBtn.style.boxShadow = '0 0 20px rgba(231, 76, 60, 0.8)';
                waiterBtn.style.opacity = '0.5';
                waiterBtn.style.boxShadow = 'none';
            }

            // Update label display
            document.getElementById('current-label').textContent =
                currentLabel === 'waiter' ? '👔 Waiter' : '🧑 Customer';
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            switch(e.key) {
                case ' ':  // Space to toggle
                    e.preventDefault();
                    currentLabel = currentLabel === 'customer' ? 'waiter' : 'customer';
                    updateLabelButtons();
                    break;
                case 'Enter':  // Enter to save and next
                    e.preventDefault();
                    labelImage(currentLabel);
                    break;
                case 'ArrowLeft':  // Left arrow for previous
                    previousImage();
                    break;
            }
        });

        function updateImage() {
            fetch('/get_image')
                .then(response => response.json())
                .then(data => {
                    if (data.image) {
                        document.getElementById('current-image').src = data.image;
                        document.getElementById('image-name').textContent = data.filename;
                        document.getElementById('current').textContent = data.index + 1;
                        document.getElementById('total').textContent = data.total;
                        document.getElementById('waiter-count').textContent = data.waiter_count;
                        document.getElementById('customer-count').textContent = data.customer_count;
                        document.getElementById('labeled-count').textContent = data.labeled_count;

                        // Update progress bar
                        const progress = ((data.index + 1) / data.total) * 100;
                        document.getElementById('progress-bar').style.width = progress + '%';

                        currentIndex = data.index;
                        total = data.total;
                    } else {
                        alert('All images labeled! 🎉');
                    }
                });
        }

        function setLabel(label) {
            currentLabel = label;
            updateLabelButtons();
        }

        function saveAndNext() {
            labelImage(currentLabel);
        }

        function labelImage(label) {
            fetch('/label', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({label: label, index: currentIndex})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Reset to customer for next image
                    currentLabel = 'customer';
                    updateLabelButtons();
                    updateImage();
                }
            });
        }

        function skipImage() {
            fetch('/skip', {method: 'POST'})
                .then(response => response.json())
                .then(data => updateImage());
        }

        function previousImage() {
            fetch('/previous', {method: 'POST'})
                .then(response => response.json())
                .then(data => updateImage());
        }

        // Initial load
        updateLabelButtons();
        updateImage();
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@app.route('/get_image')
def get_image():
    global current_index, images, labels

    if current_index < len(images):
        filename = images[current_index]
        # Convert image to base64
        import base64
        img_path = os.path.join(INPUT_DIR, filename)
        with open(img_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode()

        waiter_count = sum(1 for v in labels.values() if v == 'waiter')
        customer_count = sum(1 for v in labels.values() if v == 'customer')

        return jsonify({
            'image': f'data:image/jpeg;base64,{img_data}',
            'filename': filename,
            'index': current_index,
            'total': len(images),
            'waiter_count': waiter_count,
            'customer_count': customer_count,
            'labeled_count': len(labels)
        })
    else:
        return jsonify({'image': None})

@app.route('/label', methods=['POST'])
def label():
    global current_index, images, labels

    data = request.json
    label = data['label']

    if current_index < len(images):
        filename = images[current_index]
        old_label = labels.get(filename)  # Check if already labeled
        labels[filename] = label

        # Source file
        src = os.path.join(INPUT_DIR, filename)

        # If re-labeling, remove from old location first
        if old_label and old_label != label:
            old_dst = os.path.join(f"{OUTPUT_DIR}/{old_label}s", filename)
            if os.path.exists(old_dst):
                os.remove(old_dst)
                print(f"   Moved {filename}: {old_label} → {label}")

        # Check if file exists in other label directory and remove it
        other_label = 'customer' if label == 'waiter' else 'waiter'
        other_dst = os.path.join(f"{OUTPUT_DIR}/{other_label}s", filename)
        if os.path.exists(other_dst):
            os.remove(other_dst)
            print(f"   Removed duplicate {filename} from {other_label}s folder")

        # Copy file to correct labeled directory
        dst_dir = f"{OUTPUT_DIR}/{label}s"
        dst = os.path.join(dst_dir, filename)
        shutil.copy2(src, dst)

        # Save labels
        with open(f"{OUTPUT_DIR}/labels.json", 'w') as f:
            json.dump(labels, f, indent=2)

        current_index += 1
        return jsonify({'success': True})

    return jsonify({'success': False})

@app.route('/skip', methods=['POST'])
def skip():
    global current_index
    if current_index < len(images) - 1:
        current_index += 1
    return jsonify({'success': True})

@app.route('/previous', methods=['POST'])
def previous():
    global current_index
    if current_index > 0:
        current_index -= 1
    return jsonify({'success': True})

if __name__ == "__main__":
    setup()
    print("\n🚀 Starting labeling tool...")
    print("🌐 Open your browser at: http://localhost:5002")
    print("\n⌨️  Keyboard shortcuts:")
    print("   Space = Toggle between Waiter/Customer")
    print("   Enter = Save current label & next")
    print("   ← = Previous image")
    print("\n📌 Default label: Customer (press Space to switch to Waiter)\n")

    app.run(host='0.0.0.0', port=5002, debug=False)
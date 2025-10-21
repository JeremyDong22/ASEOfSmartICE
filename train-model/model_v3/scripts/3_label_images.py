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
INPUT_DIR = "../extracted-persons"
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

    # Get all images from all subdirectories (camera_XX folders)
    images = []
    if os.path.exists(INPUT_DIR):
        for root, dirs, files in os.walk(INPUT_DIR):
            for f in files:
                if f.endswith(('.jpg', '.png')):
                    # Store relative path from INPUT_DIR
                    rel_path = os.path.relpath(os.path.join(root, f), INPUT_DIR)
                    images.append(rel_path)

    images = sorted(images)
    total_images = len(images)

    # Filter out already labeled images to skip them
    unlabeled_images = [img for img in images if img not in labels]
    images = unlabeled_images

    print(f"📷 Total images: {total_images}")
    print(f"✅ Already labeled: {len(labels)} images")
    print(f"📝 Remaining to label: {len(images)} images")

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Image Labeling Tool</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #000000 0%, #1a1a1a 100%);
            color: #e0e0e0;
            height: 100vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .header {
            padding: 12px 20px;
            background: rgba(30, 30, 30, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }

        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            max-width: 100%;
        }

        h1 {
            font-size: 1.3rem;
            font-weight: 600;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .stats {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .stat-box {
            background: rgba(255, 255, 255, 0.05);
            padding: 8px 15px;
            border-radius: 8px;
            font-size: 0.85rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }

        .stat-box strong {
            font-size: 1.1rem;
            margin-left: 5px;
        }

        .progress-container {
            background: rgba(255, 255, 255, 0.05);
            height: 4px;
            overflow: hidden;
        }

        .progress-bar {
            background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
            height: 100%;
            transition: width 0.4s ease;
            box-shadow: 0 0 10px rgba(102, 126, 234, 0.5);
        }

        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 20px;
            overflow: hidden;
        }

        .image-container {
            width: 100%;
            height: 70vh;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 20px;
        }

        #current-image {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            border-radius: 12px;
            border: 6px solid #ef4444;
            box-shadow: 0 0 40px rgba(239, 68, 68, 0.6);
            transition: all 0.3s ease;
        }

        #current-image.waiter {
            border-color: #3b82f6;
            box-shadow: 0 0 40px rgba(59, 130, 246, 0.6);
        }

        #current-image.customer {
            border-color: #ef4444;
            box-shadow: 0 0 40px rgba(239, 68, 68, 0.6);
        }

        .label-indicator {
            text-align: center;
            margin-bottom: 15px;
            font-size: 1.1rem;
            font-weight: 600;
            padding: 10px 25px;
            border-radius: 25px;
            display: inline-block;
            transition: all 0.3s ease;
        }

        .label-indicator.waiter {
            background: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            border: 2px solid #3b82f6;
        }

        .label-indicator.customer {
            background: rgba(239, 68, 68, 0.2);
            color: #f87171;
            border: 2px solid #ef4444;
        }

        .controls {
            display: flex;
            gap: 12px;
            align-items: center;
            justify-content: center;
            flex-wrap: wrap;
            margin-top: 10px;
        }

        button {
            font-size: 0.95rem;
            padding: 10px 20px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
            font-weight: 500;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4);
        }

        button:active {
            transform: translateY(0);
        }

        .btn-waiter {
            background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
            color: white;
        }

        .btn-customer {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
        }

        .btn-back {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
        }

        .btn-save {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            padding: 10px 30px;
            font-size: 1rem;
        }

        .keyboard-hints {
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: rgba(30, 30, 30, 0.9);
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 0.75rem;
            border: 1px solid rgba(255, 255, 255, 0.1);
            backdrop-filter: blur(10px);
        }

        #image-name {
            font-size: 0.75rem;
            color: #888;
            margin-top: 5px;
            text-align: center;
        }

        @media (max-height: 800px) {
            .image-container {
                height: 65vh;
            }
        }

        @media (max-width: 768px) {
            .stats {
                gap: 8px;
            }
            .stat-box {
                padding: 6px 10px;
                font-size: 0.75rem;
            }
            h1 {
                font-size: 1.1rem;
            }
            button {
                font-size: 0.85rem;
                padding: 8px 15px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <h1>👤 Person Classification Tool</h1>
            <div class="stats">
                <div class="stat-box">
                    👔 <strong id="waiter-count">0</strong>
                </div>
                <div class="stat-box">
                    🧑 <strong id="customer-count">0</strong>
                </div>
                <div class="stat-box">
                    <span id="current">0</span>/<span id="total">0</span>
                </div>
            </div>
        </div>
        <div class="progress-container">
            <div class="progress-bar" id="progress-bar"></div>
        </div>
    </div>

    <div class="main-content">
        <div class="label-indicator customer" id="label-indicator">
            🧑 Customer
        </div>

        <div class="image-container">
            <img id="current-image" class="customer" src="" alt="Current Image">
        </div>

        <div id="image-name"></div>

        <div class="controls">
            <button class="btn-back" onclick="previousImage()">⬅️ Previous</button>
            <button class="btn-waiter" onclick="setLabel('waiter')">👔 Waiter</button>
            <button class="btn-customer" onclick="setLabel('customer')">🧑 Customer</button>
            <button class="btn-save" onclick="saveAndNext()">✅ Save & Next</button>
        </div>
    </div>

    <div class="keyboard-hints">
        ⌨️ Space=Toggle | Enter=Save | ←=Prev
    </div>

    <script>
        let currentIndex = 0;
        let total = 0;

        let currentLabel = 'customer';  // Default is customer

        // Update UI to show current selection
        function updateLabelButtons() {
            const image = document.getElementById('current-image');
            const indicator = document.getElementById('label-indicator');

            // Update image border class
            image.className = currentLabel;

            // Update label indicator
            indicator.className = `label-indicator ${currentLabel}`;
            indicator.textContent = currentLabel === 'waiter' ? '👔 Waiter' : '🧑 Customer';
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
        # Ensure subdirectory exists (for camera_XX folders)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
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
    try:
        setup()
        print("\n🚀 Starting labeling tool...")
        print("🌐 Open your browser at: http://localhost:5002")
        print("\n⌨️  Keyboard shortcuts:")
        print("   Space = Toggle between Waiter/Customer")
        print("   Enter = Save current label & next")
        print("   ← = Previous image")
        print("\n📌 Default label: Customer (press Space to switch to Waiter)\n")

        os.system('say "Labeling tool started on localhost port 5002"')
        app.run(host='0.0.0.0', port=5002, debug=False)
    except KeyboardInterrupt:
        print("\n✅ Labeling session ended by user")
        os.system('say "Labeling tool stopped"')
    except Exception as e:
        print(f"\n❌ Error: {e}")
        os.system('say "Labeling tool failed with error"')
        raise
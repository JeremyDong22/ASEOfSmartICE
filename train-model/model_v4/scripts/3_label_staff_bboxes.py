#!/usr/bin/env python3
# Version: 5.1 (Model V4 - One-Step Staff Detection)
# Web-based bounding box labeling tool for staff detection
# Draw bounding boxes around STAFF ONLY (not customers)
# Supports multiple bounding boxes per image (0, 1, or many staff)
# Stores labels in SQLite database, exports to YOLO detection format
# V5.1: Added session-based "previous" navigation to review labeled images

import os
import base64
import sqlite3
from pathlib import Path
from flask import Flask, render_template_string, jsonify, request
from datetime import datetime

app = Flask(__name__)

# Paths
INPUT_DIR = "../filtered_images_with_people"
OUTPUT_DIR = "../labeled_staff_bboxes"
DB_PATH = f"{OUTPUT_DIR}/labels.db"

# Global state
current_index = 0
images = []
db_conn = None
session_labeled = []  # Track labeled images in this session for "previous" navigation
viewing_labeled = False  # Whether currently viewing a previously labeled image
viewing_labeled_idx = -1  # Index in session_labeled list

def init_database():
    """Initialize SQLite database for storing bounding box labels"""
    global db_conn

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    db_conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cursor = db_conn.cursor()

    # Create tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_path TEXT UNIQUE NOT NULL,
            labeled BOOLEAN DEFAULT 0,
            labeled_at TIMESTAMP
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bboxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            image_id INTEGER NOT NULL,
            x REAL NOT NULL,
            y REAL NOT NULL,
            width REAL NOT NULL,
            height REAL NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (image_id) REFERENCES images(id) ON DELETE CASCADE
        )
    ''')

    db_conn.commit()
    print("✅ Database initialized")

def load_images():
    """Load all images from filtered directory"""
    global images

    if not os.path.exists(INPUT_DIR):
        print(f"❌ Input directory not found: {INPUT_DIR}")
        print("   Please run 2_filter_images_with_people.py first")
        return

    # Get all images recursively
    images = []
    for root, dirs, files in os.walk(INPUT_DIR):
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                rel_path = os.path.relpath(os.path.join(root, f), INPUT_DIR)
                images.append(rel_path)

    images = sorted(images)

    # Insert images into database if not already present
    cursor = db_conn.cursor()
    for img_path in images:
        cursor.execute('INSERT OR IGNORE INTO images (image_path) VALUES (?)', (img_path,))
    db_conn.commit()

    # Count labeled vs unlabeled
    cursor.execute('SELECT COUNT(*) FROM images WHERE labeled = 1')
    labeled_count = cursor.fetchone()[0]

    print(f"📷 Total images: {len(images)}")
    print(f"✅ Already labeled: {labeled_count}")
    print(f"📝 Remaining to label: {len(images) - labeled_count}")

def get_image_bboxes(image_path):
    """Get all bounding boxes for an image"""
    cursor = db_conn.cursor()
    cursor.execute('''
        SELECT b.id, b.x, b.y, b.width, b.height
        FROM bboxes b
        JOIN images i ON b.image_id = i.id
        WHERE i.image_path = ?
    ''', (image_path,))
    return cursor.fetchall()

def get_stats():
    """Get labeling statistics"""
    cursor = db_conn.cursor()

    # Total labeled images
    cursor.execute('SELECT COUNT(*) FROM images WHERE labeled = 1')
    labeled_images = cursor.fetchone()[0]

    # Total bounding boxes
    cursor.execute('SELECT COUNT(*) FROM bboxes')
    total_bboxes = cursor.fetchone()[0]

    # Images with staff (bbox count > 0)
    cursor.execute('''
        SELECT COUNT(DISTINCT i.id)
        FROM images i
        JOIN bboxes b ON i.id = b.image_id
        WHERE i.labeled = 1
    ''')
    images_with_staff = cursor.fetchone()[0]

    # Images without staff (labeled but no bboxes)
    images_without_staff = labeled_images - images_with_staff

    return {
        'labeled_images': labeled_images,
        'total_bboxes': total_bboxes,
        'images_with_staff': images_with_staff,
        'images_without_staff': images_without_staff
    }

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Staff Bounding Box Labeling Tool</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e0e0e0;
            height: 100vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        .header {
            padding: 12px 20px;
            background: rgba(30, 30, 40, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 2px solid rgba(59, 130, 246, 0.3);
        }

        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        h1 {
            font-size: 1.3rem;
            font-weight: 600;
            background: linear-gradient(135deg, #3b82f6 0%, #8b5cf6 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .stats {
            display: flex;
            gap: 15px;
            align-items: center;
        }

        .stat-box {
            background: rgba(59, 130, 246, 0.1);
            padding: 8px 15px;
            border-radius: 8px;
            font-size: 0.85rem;
            border: 1px solid rgba(59, 130, 246, 0.3);
        }

        .stat-box strong {
            font-size: 1.1rem;
            margin-left: 5px;
            color: #60a5fa;
        }

        .main-content {
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 20px;
            overflow: hidden;
        }

        .canvas-container {
            position: relative;
            display: inline-block;
            max-width: 95%;
            max-height: 70vh;
            margin-bottom: 15px;
            border: 3px solid #3b82f6;
            border-radius: 8px;
            box-shadow: 0 0 30px rgba(59, 130, 246, 0.4);
        }

        #canvas {
            display: block;
            cursor: crosshair;
            max-width: 100%;
            max-height: 70vh;
        }

        .bbox-list {
            background: rgba(30, 30, 40, 0.8);
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 15px;
            min-height: 40px;
            max-height: 80px;
            overflow-y: auto;
            width: 100%;
            max-width: 800px;
        }

        .bbox-item {
            display: inline-block;
            background: rgba(59, 130, 246, 0.2);
            padding: 5px 12px;
            margin: 3px;
            border-radius: 15px;
            font-size: 0.8rem;
            border: 1px solid rgba(59, 130, 246, 0.5);
        }

        .bbox-item button {
            background: none;
            border: none;
            color: #ef4444;
            cursor: pointer;
            margin-left: 8px;
            font-weight: bold;
        }

        .controls {
            display: flex;
            gap: 12px;
            align-items: center;
            justify-content: center;
            flex-wrap: wrap;
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

        .btn-save {
            background: linear-gradient(135deg, #10b981 0%, #059669 100%);
            color: white;
            padding: 10px 30px;
        }

        .btn-clear {
            background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
            color: white;
        }

        .btn-skip {
            background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
            color: white;
        }

        .btn-prev {
            background: linear-gradient(135deg, #6b7280 0%, #4b5563 100%);
            color: white;
        }

        .btn-undo {
            background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%);
            color: white;
        }

        .instructions {
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: rgba(30, 30, 40, 0.95);
            padding: 12px 18px;
            border-radius: 8px;
            font-size: 0.75rem;
            border: 1px solid rgba(59, 130, 246, 0.3);
            max-width: 300px;
        }

        .instructions h3 {
            color: #60a5fa;
            margin-bottom: 8px;
            font-size: 0.85rem;
        }

        .instructions p {
            margin: 4px 0;
            line-height: 1.4;
        }

        #image-name {
            font-size: 0.75rem;
            color: #888;
            margin-bottom: 10px;
            text-align: center;
        }

        .progress-bar-container {
            background: rgba(255, 255, 255, 0.05);
            height: 4px;
            overflow: hidden;
            margin-top: 5px;
        }

        .progress-bar {
            background: linear-gradient(90deg, #3b82f6 0%, #8b5cf6 100%);
            height: 100%;
            transition: width 0.4s ease;
        }
    </style>
</head>
<body>
    <div class="header">
        <div class="header-content">
            <h1>📦 Staff Bounding Box Labeling</h1>
            <div class="stats">
                <div class="stat-box">
                    📦 Boxes: <strong id="bbox-count">0</strong>
                </div>
                <div class="stat-box">
                    ✅ With Staff: <strong id="with-staff-count">0</strong>
                </div>
                <div class="stat-box">
                    ❌ No Staff: <strong id="no-staff-count">0</strong>
                </div>
                <div class="stat-box">
                    <span id="current">0</span>/<span id="total">0</span>
                </div>
            </div>
        </div>
        <div class="progress-bar-container">
            <div class="progress-bar" id="progress-bar"></div>
        </div>
    </div>

    <div class="main-content">
        <div id="image-name"></div>

        <div class="canvas-container">
            <canvas id="canvas"></canvas>
        </div>

        <div class="bbox-list" id="bbox-list">
            <span style="color: #888;">No bounding boxes yet. Draw boxes around staff members.</span>
        </div>

        <div class="controls">
            <button class="btn-prev" onclick="previousImage()">⬅️ Previous</button>
            <button class="btn-undo" onclick="undoLastBox()">↶ Undo Last</button>
            <button class="btn-clear" onclick="clearAllBoxes()">🗑️ Clear All</button>
            <button class="btn-next" onclick="nextImage()" id="btn-next" style="display:none; background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white;">➡️ Next</button>
            <button class="btn-camera" onclick="nextCamera()" style="background: linear-gradient(135deg, #8b5cf6 0%, #7c3aed 100%); color: white;">📷 Next Camera (Tab)</button>
            <button class="btn-save" onclick="saveAndNext()">✅ Save & Next</button>
        </div>

        <div id="review-banner" style="display:none; background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%); color: white; padding: 10px 20px; border-radius: 8px; margin-top: 15px; text-align: center;">
            📝 REVIEWING PREVIOUSLY LABELED IMAGE - Edit boxes and Save, or press Next/Previous to navigate
        </div>
    </div>

    <div class="instructions">
        <h3>📋 Instructions:</h3>
        <p><strong>1.</strong> Draw boxes around STAFF ONLY (or none if no staff)</p>
        <p><strong>2.</strong> Press Enter to save and continue</p>
        <p style="margin-top: 8px; color: #60a5fa;"><strong>⌨️ Shortcuts:</strong></p>
        <p>Enter = Save | U = Undo | Tab = Next Camera</p>
        <p>← = Previous | → = Next (review)</p>
    </div>

    <script>
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        let img = new Image();
        let currentBboxes = [];
        let isDrawing = false;
        let startX, startY;
        let currentIndex = 0;
        let total = 0;
        let scale = 1;
        let isViewingLabeled = false;

        // Load image and display
        function updateImage() {
            fetch('/get_image')
                .then(response => response.json())
                .then(data => {
                    if (data.image) {
                        img.src = data.image;
                        img.onload = () => {
                            // Calculate scale to fit canvas
                            const maxWidth = window.innerWidth * 0.9;
                            const maxHeight = window.innerHeight * 0.6;
                            scale = Math.min(maxWidth / img.width, maxHeight / img.height, 1);

                            canvas.width = img.width * scale;
                            canvas.height = img.height * scale;

                            drawImage();
                        };

                        document.getElementById('image-name').textContent = data.filename;
                        document.getElementById('current').textContent = data.index + 1;
                        document.getElementById('total').textContent = data.total;

                        // Update stats
                        document.getElementById('bbox-count').textContent = data.stats.total_bboxes;
                        document.getElementById('with-staff-count').textContent = data.stats.images_with_staff;
                        document.getElementById('no-staff-count').textContent = data.stats.images_without_staff;

                        // Progress bar
                        const progress = ((data.index + 1) / data.total) * 100;
                        document.getElementById('progress-bar').style.width = progress + '%';

                        currentIndex = data.index;
                        total = data.total;
                        currentBboxes = data.bboxes || [];
                        isViewingLabeled = data.viewing_labeled || false;
                        updateBboxList();

                        // Show/hide review mode UI elements
                        const reviewBanner = document.getElementById('review-banner');
                        const btnNext = document.getElementById('btn-next');
                        if (isViewingLabeled) {
                            reviewBanner.style.display = 'block';
                            btnNext.style.display = 'inline-block';
                        } else {
                            reviewBanner.style.display = 'none';
                            btnNext.style.display = 'none';
                        }
                    } else {
                        alert('All images labeled! 🎉');
                    }
                });
        }

        function drawImage() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            ctx.drawImage(img, 0, 0, canvas.width, canvas.height);

            // Draw existing bboxes
            ctx.strokeStyle = '#3b82f6';
            ctx.lineWidth = 3;
            currentBboxes.forEach(bbox => {
                ctx.strokeRect(bbox.x * scale, bbox.y * scale, bbox.width * scale, bbox.height * scale);
            });
        }

        function updateBboxList() {
            const list = document.getElementById('bbox-list');
            if (currentBboxes.length === 0) {
                list.innerHTML = '<span style="color: #888;">No bounding boxes yet. Draw boxes around staff members.</span>';
            } else {
                list.innerHTML = currentBboxes.map((bbox, idx) =>
                    `<span class="bbox-item">Box ${idx + 1}: ${Math.round(bbox.width)}×${Math.round(bbox.height)}px <button onclick="deleteBox(${idx})">✕</button></span>`
                ).join('');
            }
        }

        // Mouse events for drawing bboxes
        canvas.addEventListener('mousedown', (e) => {
            isDrawing = true;
            const rect = canvas.getBoundingClientRect();
            startX = (e.clientX - rect.left) / scale;
            startY = (e.clientY - rect.top) / scale;
        });

        canvas.addEventListener('mousemove', (e) => {
            if (!isDrawing) return;

            const rect = canvas.getBoundingClientRect();
            const currentX = (e.clientX - rect.left) / scale;
            const currentY = (e.clientY - rect.top) / scale;

            drawImage();

            // Draw current box being drawn
            ctx.strokeStyle = '#10b981';
            ctx.lineWidth = 3;
            ctx.setLineDash([5, 5]);
            ctx.strokeRect(startX * scale, startY * scale, (currentX - startX) * scale, (currentY - startY) * scale);
            ctx.setLineDash([]);
        });

        canvas.addEventListener('mouseup', (e) => {
            if (!isDrawing) return;
            isDrawing = false;

            const rect = canvas.getBoundingClientRect();
            const endX = (e.clientX - rect.left) / scale;
            const endY = (e.clientY - rect.top) / scale;

            const width = endX - startX;
            const height = endY - startY;

            // Only add if box is large enough (prevent accidental clicks)
            if (Math.abs(width) > 20 && Math.abs(height) > 20) {
                // Normalize bbox (handle negative width/height)
                const bbox = {
                    x: width > 0 ? startX : endX,
                    y: height > 0 ? startY : endY,
                    width: Math.abs(width),
                    height: Math.abs(height)
                };
                currentBboxes.push(bbox);
                updateBboxList();
                drawImage();
            }
        });

        function deleteBox(index) {
            currentBboxes.splice(index, 1);
            updateBboxList();
            drawImage();
        }

        function undoLastBox() {
            if (currentBboxes.length > 0) {
                currentBboxes.pop();
                updateBboxList();
                drawImage();
            }
        }

        function clearAllBoxes() {
            if (currentBboxes.length > 0 && confirm('Clear all bounding boxes?')) {
                currentBboxes = [];
                updateBboxList();
                drawImage();
            }
        }

        function saveAndNext() {
            fetch('/save_labels', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    index: currentIndex,
                    bboxes: currentBboxes
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    currentBboxes = [];
                    updateImage();
                }
            });
        }

        function previousImage() {
            fetch('/previous', {method: 'POST'})
                .then(response => response.json())
                .then(data => updateImage());
        }

        function nextImage() {
            fetch('/next', {method: 'POST'})
                .then(response => response.json())
                .then(data => updateImage());
        }

        function nextCamera() {
            fetch('/next_camera', {method: 'POST'})
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        currentBboxes = [];
                        updateImage();
                    } else {
                        alert(data.message || 'No more cameras with unlabeled images');
                    }
                });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            if (e.target.tagName === 'INPUT') return;

            switch(e.key) {
                case 'Enter':
                    e.preventDefault();
                    saveAndNext();
                    break;
                case 'u':
                case 'U':
                    e.preventDefault();
                    undoLastBox();
                    break;
                case 'ArrowLeft':
                    e.preventDefault();
                    previousImage();
                    break;
                case 'ArrowRight':
                    e.preventDefault();
                    if (isViewingLabeled) nextImage();
                    break;
                case 'Tab':
                    e.preventDefault();
                    nextCamera();
                    break;
            }
        });

        // Initial load
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
    global current_index, viewing_labeled, viewing_labeled_idx

    cursor = db_conn.cursor()

    # If viewing a previously labeled image from this session
    if viewing_labeled and viewing_labeled_idx >= 0 and viewing_labeled_idx < len(session_labeled):
        image_path = session_labeled[viewing_labeled_idx]

        # Get image info from database
        cursor.execute('SELECT id FROM images WHERE image_path = ?', (image_path,))
        result = cursor.fetchone()

        if result:
            image_id = result[0]

            # Load image as base64
            img_full_path = os.path.join(INPUT_DIR, image_path)
            with open(img_full_path, 'rb') as f:
                img_data = base64.b64encode(f.read()).decode()

            # Get existing bboxes for this image
            cursor.execute('''
                SELECT x, y, width, height FROM bboxes
                WHERE image_id = ?
            ''', (image_id,))
            bboxes = [{'x': row[0], 'y': row[1], 'width': row[2], 'height': row[3]} for row in cursor.fetchall()]

            # Get total count
            cursor.execute('SELECT COUNT(*) FROM images WHERE labeled = 0')
            total_unlabeled = cursor.fetchone()[0]

            stats = get_stats()

            return jsonify({
                'image': f'data:image/jpeg;base64,{img_data}',
                'filename': f'[REVIEWING] {image_path}',
                'index': viewing_labeled_idx,
                'total': len(session_labeled),
                'bboxes': bboxes,
                'stats': stats,
                'viewing_labeled': True
            })

    # Get next unlabeled image
    cursor.execute('''
        SELECT id, image_path FROM images
        WHERE labeled = 0
        ORDER BY image_path
        LIMIT 1 OFFSET ?
    ''', (current_index,))

    result = cursor.fetchone()

    if result:
        image_id, image_path = result

        # Load image as base64
        img_full_path = os.path.join(INPUT_DIR, image_path)
        with open(img_full_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode()

        # Get existing bboxes for this image
        cursor.execute('''
            SELECT x, y, width, height FROM bboxes
            WHERE image_id = ?
        ''', (image_id,))
        bboxes = [{'x': row[0], 'y': row[1], 'width': row[2], 'height': row[3]} for row in cursor.fetchall()]

        # Get total count
        cursor.execute('SELECT COUNT(*) FROM images WHERE labeled = 0')
        total_unlabeled = cursor.fetchone()[0]

        stats = get_stats()

        return jsonify({
            'image': f'data:image/jpeg;base64,{img_data}',
            'filename': image_path,
            'index': current_index,
            'total': total_unlabeled,
            'bboxes': bboxes,
            'stats': stats,
            'viewing_labeled': False
        })
    else:
        return jsonify({'image': None})

@app.route('/save_labels', methods=['POST'])
def save_labels():
    global current_index, session_labeled, viewing_labeled, viewing_labeled_idx

    data = request.json
    bboxes = data.get('bboxes', [])

    cursor = db_conn.cursor()

    # If we're viewing a previously labeled image, update it
    if viewing_labeled and viewing_labeled_idx >= 0 and viewing_labeled_idx < len(session_labeled):
        image_path = session_labeled[viewing_labeled_idx]
        cursor.execute('SELECT id FROM images WHERE image_path = ?', (image_path,))
        result = cursor.fetchone()

        if result:
            image_id = result[0]

            # Delete existing bboxes for this image
            cursor.execute('DELETE FROM bboxes WHERE image_id = ?', (image_id,))

            # Insert new bboxes
            for bbox in bboxes:
                cursor.execute('''
                    INSERT INTO bboxes (image_id, x, y, width, height)
                    VALUES (?, ?, ?, ?, ?)
                ''', (image_id, bbox['x'], bbox['y'], bbox['width'], bbox['height']))

            db_conn.commit()

            print(f"✅ Updated: {image_path} with {len(bboxes)} bounding box(es)")

            # Move forward in session history or back to unlabeled
            if viewing_labeled_idx < len(session_labeled) - 1:
                viewing_labeled_idx += 1
            else:
                # Back to normal unlabeled mode
                viewing_labeled = False
                viewing_labeled_idx = -1

            return jsonify({'success': True})

        return jsonify({'success': False})

    # Get current unlabeled image
    cursor.execute('''
        SELECT id, image_path FROM images
        WHERE labeled = 0
        ORDER BY image_path
        LIMIT 1 OFFSET ?
    ''', (current_index,))

    result = cursor.fetchone()

    if result:
        image_id, image_path = result

        # Delete existing bboxes for this image
        cursor.execute('DELETE FROM bboxes WHERE image_id = ?', (image_id,))

        # Insert new bboxes
        for bbox in bboxes:
            cursor.execute('''
                INSERT INTO bboxes (image_id, x, y, width, height)
                VALUES (?, ?, ?, ?, ?)
            ''', (image_id, bbox['x'], bbox['y'], bbox['width'], bbox['height']))

        # Mark image as labeled
        cursor.execute('''
            UPDATE images SET labeled = 1, labeled_at = ? WHERE id = ?
        ''', (datetime.now().isoformat(), image_id))

        db_conn.commit()

        # Track this image in session for "previous" navigation
        session_labeled.append(image_path)

        # Move to next unlabeled image (reset index to 0 to get next unlabeled)
        current_index = 0

        print(f"✅ Labeled: {image_path} with {len(bboxes)} bounding box(es) (session: {len(session_labeled)} labeled)")

        return jsonify({'success': True})

    return jsonify({'success': False})

@app.route('/previous', methods=['POST'])
def previous():
    global current_index, viewing_labeled, viewing_labeled_idx, session_labeled

    # If viewing labeled images, go back in history
    if viewing_labeled:
        if viewing_labeled_idx > 0:
            viewing_labeled_idx -= 1
        # Stay at first labeled image, don't go negative
        return jsonify({'success': True})

    # Load all labeled images from database if session_labeled is empty
    if len(session_labeled) == 0:
        cursor = db_conn.cursor()
        cursor.execute('''
            SELECT image_path FROM images
            WHERE labeled = 1
            ORDER BY labeled_at ASC
        ''')
        session_labeled = [row[0] for row in cursor.fetchall()]
        print(f"📋 Loaded {len(session_labeled)} previously labeled images for navigation")

    # If we have labeled images, start viewing them
    if len(session_labeled) > 0:
        viewing_labeled = True
        viewing_labeled_idx = len(session_labeled) - 1  # Start at most recent
        return jsonify({'success': True})

    # Otherwise try to go back in unlabeled (doesn't help much but maintain old behavior)
    if current_index > 0:
        current_index -= 1
    return jsonify({'success': True})

@app.route('/next', methods=['POST'])
def next_image():
    global viewing_labeled, viewing_labeled_idx

    # If viewing labeled images, move forward or exit review mode
    if viewing_labeled:
        if viewing_labeled_idx < len(session_labeled) - 1:
            viewing_labeled_idx += 1
        else:
            # Exit review mode, back to unlabeled
            viewing_labeled = False
            viewing_labeled_idx = -1
        return jsonify({'success': True})

    # In normal mode, next is same as save without saving
    return jsonify({'success': True})

@app.route('/next_camera', methods=['POST'])
def next_camera():
    global current_index, viewing_labeled, viewing_labeled_idx

    # Exit review mode if active
    viewing_labeled = False
    viewing_labeled_idx = -1

    cursor = db_conn.cursor()

    # Get current image to find current channel
    cursor.execute('''
        SELECT image_path FROM images
        WHERE labeled = 0
        ORDER BY image_path
        LIMIT 1 OFFSET ?
    ''', (current_index,))

    result = cursor.fetchone()
    if not result:
        return jsonify({'success': False, 'message': 'No more unlabeled images'})

    current_path = result[0]

    # Extract current channel (e.g., "channel_1" from "channel_1/image.jpg")
    current_channel = current_path.split('/')[0] if '/' in current_path else ''

    # Find next channel with unlabeled images
    cursor.execute('''
        SELECT DISTINCT substr(image_path, 1, instr(image_path, '/') - 1) as channel
        FROM images
        WHERE labeled = 0
        AND substr(image_path, 1, instr(image_path, '/') - 1) > ?
        ORDER BY channel
        LIMIT 1
    ''', (current_channel,))

    next_channel_result = cursor.fetchone()

    if next_channel_result:
        next_channel = next_channel_result[0]

        # Find the index offset for the first image in this channel
        cursor.execute('''
            SELECT COUNT(*) FROM images
            WHERE labeled = 0
            AND image_path < (
                SELECT MIN(image_path) FROM images
                WHERE labeled = 0 AND image_path LIKE ? || '/%'
            )
            ORDER BY image_path
        ''', (next_channel,))

        offset_result = cursor.fetchone()
        current_index = offset_result[0] if offset_result else 0

        print(f"📷 Jumped to camera: {next_channel}")
        return jsonify({'success': True, 'channel': next_channel})
    else:
        # Wrap around to first channel
        cursor.execute('''
            SELECT DISTINCT substr(image_path, 1, instr(image_path, '/') - 1) as channel
            FROM images
            WHERE labeled = 0
            ORDER BY channel
            LIMIT 1
        ''')

        first_channel_result = cursor.fetchone()
        if first_channel_result and first_channel_result[0] != current_channel:
            current_index = 0
            print(f"📷 Wrapped to first camera: {first_channel_result[0]}")
            return jsonify({'success': True, 'channel': first_channel_result[0]})

        return jsonify({'success': False, 'message': 'Only one camera has unlabeled images'})

if __name__ == "__main__":
    try:
        print("\n🚀 Starting Staff Bounding Box Labeling Tool...")
        print("=" * 70)

        init_database()
        load_images()

        if not images:
            print("\n❌ No images found. Please run 2_filter_images_with_people.py first")
            exit(1)

        print("\n🌐 Open your browser at: http://localhost:5003")
        print("\n📋 Instructions:")
        print("   1. Click and drag on the image to draw bounding boxes around STAFF ONLY")
        print("   2. Draw multiple boxes if there are multiple staff members")
        print("   3. Click 'Skip' if there are NO staff in the image")
        print("   4. Click 'Save & Next' when done labeling the image")
        print("\n⌨️  Keyboard shortcuts:")
        print("   Enter = Save & Next")
        print("   U = Undo last box")
        print("   S = Skip (no staff)")
        print("   ← = Previous image")
        print("\n📦 Label ONLY staff members (people wearing hats/uniforms)")
        print("   DO NOT label customers!")
        print("=" * 70)

        os.system('say "Bounding box labeling tool started on localhost port 5003"')
        app.run(host='0.0.0.0', port=5003, debug=False)

    except KeyboardInterrupt:
        print("\n\n✅ Labeling session ended by user")
        if db_conn:
            db_conn.close()
        os.system('say "Labeling tool stopped"')
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        if db_conn:
            db_conn.close()
        os.system('say "Labeling tool failed with error"')
        raise

#!/usr/bin/env python3
# Version: 1.0
# Detect duplicate or highly similar images using OpenCV

import cv2
import os
import numpy as np
from pathlib import Path
import hashlib
from collections import defaultdict

INPUT_DIR = "../extracted-persons"

def get_file_hash(filepath):
    """Get MD5 hash of file (detects exact duplicates)"""
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def get_image_dhash(filepath, hash_size=8):
    """Get difference hash using OpenCV (detects similar images)"""
    try:
        img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None

        # Resize to hash_size+1 x hash_size
        resized = cv2.resize(img, (hash_size + 1, hash_size))

        # Compute horizontal gradient
        diff = resized[:, 1:] > resized[:, :-1]

        # Convert to hash string
        return ''.join(['1' if d else '0' for row in diff for d in row])
    except:
        return None

def get_image_phash(filepath, hash_size=8):
    """Get perceptual hash using OpenCV (detects visually similar images)"""
    try:
        img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None

        # Resize to hash_size x hash_size
        resized = cv2.resize(img, (hash_size, hash_size))

        # DCT transform
        dct = cv2.dct(np.float32(resized))

        # Take top-left 8x8
        dct_low = dct[:hash_size, :hash_size]

        # Compute median
        med = np.median(dct_low)

        # Convert to hash
        diff = dct_low > med
        return ''.join(['1' if d else '0' for row in diff for d in row])
    except:
        return None

def analyze_duplicates():
    """Analyze duplicate images in the dataset"""
    print("🔍 Analyzing duplicate images...\n")

    # Get all images
    all_images = []
    for root, dirs, files in os.walk(INPUT_DIR):
        for f in files:
            if f.endswith(('.jpg', '.png')):
                all_images.append(os.path.join(root, f))

    print(f"📁 Total images: {len(all_images)}\n")

    # Method 1: Exact file duplicates (MD5 hash)
    print("=" * 60)
    print("METHOD 1: Exact File Duplicates (MD5)")
    print("=" * 60)
    file_hashes = defaultdict(list)

    for img_path in all_images:
        file_hash = get_file_hash(img_path)
        file_hashes[file_hash].append(img_path)

    exact_duplicates = {h: paths for h, paths in file_hashes.items() if len(paths) > 1}
    exact_dup_count = sum(len(paths) - 1 for paths in exact_duplicates.values())

    print(f"🔴 Exact duplicates found: {exact_dup_count} duplicate files")
    print(f"   (from {len(exact_duplicates)} unique images)")

    if exact_duplicates:
        print("\n   Sample exact duplicates:")
        for i, (hash_val, paths) in enumerate(list(exact_duplicates.items())[:3]):
            print(f"\n   Group {i+1}: {len(paths)} identical files")
            for p in paths[:3]:
                print(f"      - {os.path.basename(p)}")

    # Method 2: Perceptual hash (visually similar)
    print("\n" + "=" * 60)
    print("METHOD 2: Visually Similar Images (Perceptual Hash)")
    print("=" * 60)
    phashes = defaultdict(list)

    for img_path in all_images:
        phash = get_image_phash(img_path)
        if phash:
            phashes[phash].append(img_path)

    visual_duplicates = {h: paths for h, paths in phashes.items() if len(paths) > 1}
    visual_dup_count = sum(len(paths) - 1 for paths in visual_duplicates.values())

    print(f"🟡 Visually similar images: {visual_dup_count} similar files")
    print(f"   (from {len(visual_duplicates)} unique visual patterns)")

    if visual_duplicates:
        print("\n   Sample visually similar groups:")
        for i, (hash_val, paths) in enumerate(list(visual_duplicates.items())[:3]):
            print(f"\n   Group {i+1}: {len(paths)} similar files")
            for p in paths[:3]:
                print(f"      - {os.path.basename(p)}")

    # Method 3: Difference hash (very similar with slight variations)
    print("\n" + "=" * 60)
    print("METHOD 3: Nearly Identical Images (Difference Hash)")
    print("=" * 60)
    dhashes = defaultdict(list)

    for img_path in all_images:
        dhash = get_image_dhash(img_path)
        if dhash:
            dhashes[dhash].append(img_path)

    near_duplicates = {h: paths for h, paths in dhashes.items() if len(paths) > 1}
    near_dup_count = sum(len(paths) - 1 for paths in near_duplicates.values())

    print(f"🟠 Nearly identical images: {near_dup_count} similar files")
    print(f"   (from {len(near_duplicates)} unique patterns)")

    if near_duplicates:
        print("\n   Sample nearly identical groups:")
        for i, (hash_val, paths) in enumerate(list(near_duplicates.items())[:3]):
            print(f"\n   Group {i+1}: {len(paths)} similar files")
            for p in paths[:3]:
                print(f"      - {os.path.basename(p)}")

    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    print(f"Total images: {len(all_images)}")
    print(f"Exact duplicates: {exact_dup_count} ({exact_dup_count/len(all_images)*100:.1f}%)")
    print(f"Visually similar: {visual_dup_count} ({visual_dup_count/len(all_images)*100:.1f}%)")
    print(f"Nearly identical: {near_dup_count} ({near_dup_count/len(all_images)*100:.1f}%)")

    unique_after_dedup = len(all_images) - visual_dup_count
    print(f"\n💡 After removing visually similar images:")
    print(f"   Remaining unique images: ~{unique_after_dedup}")
    print(f"   Reduction: {visual_dup_count} images ({visual_dup_count/len(all_images)*100:.1f}%)")

    return {
        'total': len(all_images),
        'exact_duplicates': exact_dup_count,
        'visual_duplicates': visual_dup_count,
        'near_duplicates': near_dup_count,
        'exact_groups': exact_duplicates,
        'visual_groups': visual_duplicates,
        'near_groups': near_duplicates
    }

if __name__ == "__main__":
    try:
        results = analyze_duplicates()
        print("\n✅ Analysis complete!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

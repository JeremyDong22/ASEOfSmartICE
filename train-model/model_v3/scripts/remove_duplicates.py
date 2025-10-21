#!/usr/bin/env python3
# Version: 1.0
# Remove duplicate images and keep only unique ones

import cv2
import os
import hashlib
from collections import defaultdict
import shutil

INPUT_DIR = "../extracted-persons"
LABELED_DIR = "../labeled-persons"

def get_file_hash(filepath):
    """Get MD5 hash of file"""
    with open(filepath, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()

def remove_duplicates():
    """Remove duplicate images, keeping only the first occurrence"""
    print("🗑️  Starting duplicate removal...\n")

    # Get all images
    all_images = []
    for root, dirs, files in os.walk(INPUT_DIR):
        for f in files:
            if f.endswith(('.jpg', '.png')):
                all_images.append(os.path.join(root, f))

    print(f"📁 Total images found: {len(all_images)}")

    # Group by hash
    file_hashes = defaultdict(list)
    for img_path in all_images:
        file_hash = get_file_hash(img_path)
        file_hashes[file_hash].append(img_path)

    # Find duplicates
    duplicates_to_remove = []
    for hash_val, paths in file_hashes.items():
        if len(paths) > 1:
            # Keep the first one, remove the rest
            duplicates_to_remove.extend(paths[1:])

    print(f"🔍 Found {len(duplicates_to_remove)} duplicate files to remove")
    print(f"✅ Will keep {len(all_images) - len(duplicates_to_remove)} unique images\n")

    # Remove duplicates
    if duplicates_to_remove:
        print("🗑️  Removing duplicates...")
        for i, dup_path in enumerate(duplicates_to_remove, 1):
            try:
                os.remove(dup_path)
                if i % 50 == 0:
                    print(f"   Removed {i}/{len(duplicates_to_remove)} files...")
            except Exception as e:
                print(f"   ⚠️  Failed to remove {dup_path}: {e}")

        print(f"✅ Removed {len(duplicates_to_remove)} duplicate files")

    # Clean up labeled-persons directory
    print("\n🧹 Cleaning labeled-persons directory...")

    if os.path.exists(LABELED_DIR):
        # Remove all subdirectories and files
        for item in os.listdir(LABELED_DIR):
            item_path = os.path.join(LABELED_DIR, item)
            try:
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"   📁 Removed directory: {item}")
                else:
                    os.remove(item_path)
                    print(f"   📄 Removed file: {item}")
            except Exception as e:
                print(f"   ⚠️  Failed to remove {item}: {e}")

        # Recreate clean structure
        os.makedirs(f"{LABELED_DIR}/waiters", exist_ok=True)
        os.makedirs(f"{LABELED_DIR}/customers", exist_ok=True)
        print("✅ Recreated clean labeled-persons structure")

    # Final summary
    remaining_images = []
    for root, dirs, files in os.walk(INPUT_DIR):
        for f in files:
            if f.endswith(('.jpg', '.png')):
                remaining_images.append(os.path.join(root, f))

    print("\n" + "=" * 60)
    print("📊 FINAL SUMMARY")
    print("=" * 60)
    print(f"Original images: {len(all_images)}")
    print(f"Duplicates removed: {len(duplicates_to_remove)}")
    print(f"Remaining unique images: {len(remaining_images)}")
    print(f"Reduction: {len(duplicates_to_remove)/len(all_images)*100:.1f}%")
    print(f"\n✅ labeled-persons directory cleaned")
    print(f"📂 Ready for fresh labeling with {len(remaining_images)} images!")

if __name__ == "__main__":
    try:
        remove_duplicates()
        print("\n🎉 Cleanup complete!")
        os.system('say "Duplicate removal completed"')
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        os.system('say "Duplicate removal failed"')

# Supabase Video Upload Status Documentation

*Last Updated: 2025-10-22 20:20 CST*

## Overview

This document tracks the status of video uploads to Supabase storage bucket (ASE) and provides troubleshooting guidance for the video streaming system.

## Current Bucket Contents

### Successfully Uploaded Files

#### Test Files (2025-10-22)
- `test_uploads/test_20251022_200622.txt` - Test connection file (41 bytes)
- `videos/test/test_sample_camera_22_20251022_195212.mp4` - 10MB video sample

#### Historical Image Captures (2025-10-20)
- Multiple JPG screenshots from cameras 22, 24, 26, 29, 35, and 36
- These are single-frame captures, not video streams
- Sizes range from ~100KB to ~800KB per image

## Video Capture Results

### Local Storage (Successful)
Videos successfully captured and stored locally at:
`/home/smartahc/smartice/ASEOfSmartICE/test-model/linux_rtx_video_streaming/videos/`

| Camera | Filename | Duration | Size | Status |
|--------|----------|----------|------|--------|
| Camera 22 | camera_22_20251022_195212.mp4 | 298.8s (5.0 min) | 483 MB | ✅ Local Only |
| Camera 35 | camera_35_20251022_195212.mp4 | 300.1s (5.0 min) | 395 MB | ✅ Local Only |

### Supabase Upload (Failed)
- **Total Size**: 878 MB
- **Upload Status**: ❌ Failed
- **Failure Reasons**:
  1. Initial attempt: Invalid/expired credentials
  2. Manual retry: Timeout after 10 minutes

## Issues Identified & Fixed

### 1. Authentication Issue (FIXED)
**Problem**: Original ANON_KEY was expired
```python
# Old (expired) key
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...2MDQyMjMwNDcxXQ"

# New (valid) key - Updated 2025-10-22
SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...2MDU5NzI0MDc4XQ"
```

### 2. File Size Limitations
**Problem**: Large video files (400-500 MB) timeout during upload
**Current Workaround**: Upload first 10MB as test sample
**Recommended Solutions**:
- Implement chunked upload
- Compress videos before upload
- Use background upload process
- Consider streaming upload approach

## File Structure

```
test-model/linux_rtx_video_streaming/
├── CLAUDE.md                          # Module documentation
├── SUPABASE_STATUS.md                  # This file
├── capture_video_streams.py            # Main capture script (credentials updated)
├── test_supabase_upload.py            # Connection test script
├── upload_existing_videos.py          # Bulk upload utility
├── manual_video_upload_test.py        # Test script with size limiting
└── videos/                             # Local video storage
    ├── camera_22_20251022_195212.mp4  # 483 MB
    └── camera_35_20251022_195212.mp4  # 395 MB
```

## Database Schema

### Table: `ase_video_stream`
| Column | Type | Description |
|--------|------|-------------|
| video_id | uuid | Primary key |
| video_url | text | Public URL to video |
| camera_name | text | Camera identifier |
| capture_timestamp | timestamptz | When captured |
| resolution | text | Video resolution |
| file_size_mb | numeric | File size in MB |
| duration_seconds | integer | Video duration |
| fps | integer | Frames per second |
| created_at | timestamptz | Record creation time |

**Current Records**: 0 (no successful video uploads yet)

## Scripts Status

| Script | Purpose | Status | Notes |
|--------|---------|--------|-------|
| capture_video_streams.py | Main capture & upload | ✅ Fixed | Updated credentials |
| test_supabase_upload.py | Test connection | ✅ Working | Validates credentials |
| upload_existing_videos.py | Upload captured videos | ⚠️ Timeout | Large file issue |
| manual_video_upload_test.py | Test with size limit | ✅ Working | 10MB limit works |

## Testing Results

### Connection Test
```bash
python3 test_supabase_upload.py
# Result: ✅ Success - Small text file uploaded
```

### Video Sample Upload
```bash
python3 manual_video_upload_test.py
# Result: ✅ Success - 10MB video sample uploaded
```

### Full Video Upload
```bash
python3 upload_existing_videos.py
# Result: ❌ Timeout after 10 minutes
```

## Recommendations

### Immediate Actions
1. ✅ Update credentials in all scripts (COMPLETED)
2. ✅ Test connection with small files (COMPLETED)
3. ⏳ Implement chunked upload for large files

### Future Improvements
1. **Video Compression**
   - Reduce bitrate for smaller file sizes
   - Consider H.264 encoding optimization
   - Target 100-200 MB per 5-minute video

2. **Upload Strategy**
   - Implement resumable uploads
   - Add progress tracking
   - Use multipart upload for files >100MB
   - Consider background worker process

3. **Monitoring**
   - Add upload status logging
   - Implement retry mechanism
   - Create upload queue system

## Troubleshooting Guide

### Issue: Upload Fails with 403 Error
**Solution**: Update ANON_KEY in script to current valid key

### Issue: Upload Times Out
**Solutions**:
1. Reduce video file size through compression
2. Upload in smaller chunks
3. Use background process for upload
4. Check network bandwidth

### Issue: Videos Not Visible in Bucket
**Check**:
1. Verify upload completed (check logs)
2. Check database table for metadata
3. Verify correct bucket name (ASE)
4. Ensure proper file path structure

## Contact & Support

For issues with:
- **Supabase Configuration**: Check `supabase_mcp_setup.md`
- **Video Capture**: Review `CLAUDE.md` in this directory
- **Network/Hardware**: Contact system administrator

---

*Note: This document should be updated whenever significant changes are made to the video upload system or when new issues are discovered and resolved.*
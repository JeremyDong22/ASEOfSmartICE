# Performance Comparison: 20fps vs 5fps Processing
# Created: 2025-11-13
# Purpose: Compare processing performance at different frame rates

import json
from datetime import timedelta

print("=" * 80)
print("RTX 3060 性能对比分析 - 20fps vs 5fps Processing")
print("=" * 80)
print()

# Test video properties
video_duration = 300.05  # seconds (5 minutes)
video_size_mb = 395  # MB
video_resolution = "1920x1080"
original_fps = 20
total_frames = 6001

print("【测试视频】Test Video:")
print(f"  Duration:     {video_duration:.2f}s ({video_duration/60:.2f} minutes)")
print(f"  Resolution:   {video_resolution}")
print(f"  Original FPS: {original_fps}")
print(f"  Total Frames: {total_frames:,}")
print(f"  File Size:    {video_size_mb} MB")
print()

# Test Results
tests = {
    "20fps (全帧处理)": {
        "processing_time": 480,  # 8 minutes
        "frames_processed": 6001,
        "processing_fps": 12.5,
        "realtime_factor": 0.625,
    },
    "5fps (跳帧x4)": {
        "processing_time": 92.71,  # 1.5 minutes
        "frames_processed": 1501,  # Every 4th frame
        "processing_fps": 16.19,
        "realtime_factor": 3.24,  # 300.05s / 92.71s
    }
}

print("=" * 80)
print("【性能对比】Performance Comparison")
print("=" * 80)
print()

for test_name, data in tests.items():
    proc_time = data["processing_time"]
    proc_fps = data["processing_fps"]
    rt_factor = data["realtime_factor"]
    frames = data["frames_processed"]

    print(f"{test_name}:")
    print(f"  处理帧数:         {frames:,} frames")
    print(f"  处理时间:         {proc_time:.2f}s ({proc_time/60:.2f} minutes)")
    print(f"  处理FPS:          {proc_fps:.2f} fps")
    print(f"  实时系数:         {rt_factor:.2f}x")
    if rt_factor > 1:
        print(f"  ✅ 比实时播放快 {rt_factor:.2f}倍")
    else:
        print(f"  ❌ 比实时播放慢 {1/rt_factor:.2f}倍")
    print()

# Calculate speedup
speedup = tests["20fps (全帧处理)"]["processing_time"] / tests["5fps (跳帧x4)"]["processing_time"]
print(f"🚀 加速比: {speedup:.2f}x (5fps相比20fps提速 {speedup:.1f}倍)")
print()

# Production Scenario with 5fps
print("=" * 80)
print("【生产环境计算 - 5fps处理】Production Calculation")
print("=" * 80)
print()

cameras = 10
hours_per_day = 10
total_video_seconds = cameras * hours_per_day * 3600

rt_factor_5fps = tests["5fps (跳帧x4)"]["realtime_factor"]

print(f"需求: {cameras}个摄像头 × {hours_per_day}小时/天 = {cameras * hours_per_day}小时视频")
print()

# Single thread
single_thread_time = total_video_seconds / rt_factor_5fps
single_thread_hours = single_thread_time / 3600

print("【单线程处理】Single Thread:")
print(f"  总视频时长:       {total_video_seconds/3600:.1f} hours")
print(f"  处理时间:         {single_thread_hours:.2f} hours ({single_thread_hours*60:.0f} minutes)")
print(f"  可行性:           {'✅ 可行 (<24h)' if single_thread_hours <= 24 else '❌ 不可行 (>24h)'}")
print()

# Multi-thread scenarios
print("【多线程处理方案】Multi-threading Scenarios:")
print()

thread_configs = [
    (2, "双线程", 0.9),
    (4, "四线程", 0.75),
    (5, "五线程", 0.7),
    (10, "十线程 (每摄像头1线程)", 0.5),
]

for threads, desc, efficiency in thread_configs:
    effective_speedup = rt_factor_5fps * threads * efficiency
    multi_time = total_video_seconds / effective_speedup
    multi_hours = multi_time / 3600

    print(f"  {desc} (效率{efficiency*100:.0f}%):")
    print(f"    有效加速:       {effective_speedup:.2f}x 实时")
    print(f"    处理时间:       {multi_hours:.2f}小时 ({multi_hours*60:.0f}分钟)")
    print(f"    可行性:         {'✅ 可行' if multi_hours <= 24 else '❌ 超时'}")
    print()

# Storage calculation
print("=" * 80)
print("【存储需求】Storage Requirements")
print("=" * 80)
print()

mb_per_minute = (video_size_mb / video_duration) * 60
gb_per_hour = (mb_per_minute * 60) / 1024
daily_input_storage = cameras * hours_per_day * gb_per_hour

print(f"  原始视频码率:     {gb_per_hour:.2f} GB/hour")
print(f"  每日原始视频:     {daily_input_storage:.2f} GB ({cameras} cameras × {hours_per_day}h)")
print()

# Recommendations
print("=" * 80)
print("【结论与建议】Conclusions & Recommendations")
print("=" * 80)
print()

print("✅ 5fps处理方案可行性分析:")
print()
print("1. 单线程5fps处理:")
print(f"   - 100小时视频需要 {single_thread_hours:.1f}小时")
print(f"   - {'✅ 可在24小时内完成' if single_thread_hours <= 24 else '❌ 超过24小时'}")
print()

# Find optimal config
optimal = None
for threads, desc, efficiency in thread_configs:
    effective_speedup = rt_factor_5fps * threads * efficiency
    multi_time = (total_video_seconds / effective_speedup) / 3600
    if multi_time <= 24 and optimal is None:
        optimal = (threads, desc, multi_time)

if optimal:
    threads, desc, hours = optimal
    print(f"2. 推荐配置: {desc}")
    print(f"   - 处理时间: {hours:.2f}小时/天")
    print(f"   - GPU利用率: {(hours/24)*100:.1f}%")
    print(f"   - 可以在 {hours:.1f}小时内处理完当天所有视频")
else:
    print("2. 建议增加GPU数量或进一步优化")

print()
print("3. 检测准确性:")
print("   - 5fps (每0.2秒一帧) 对于人员状态检测足够")
print("   - 状态变化通常持续数秒，不会遗漏关键事件")
print("   - 如需更高精度，可针对关键时段提升到10fps")
print()

print("4. 进一步优化建议:")
print("   - 使用YOLOv8n替代YOLOv8m: 额外提速2-3x")
print("   - TensorRT优化: 额外提速1.5-2x")
print("   - 降分辨率到720p: 额外提速1.5x")
print("   - 组合优化可能达到 10-15x 总体加速")
print()

# Time breakdown
print("=" * 80)
print("【处理时间分解】Processing Time Breakdown (5fps)")
print("=" * 80)
print()
print("  阶段1 (人员检测):     14.5ms/frame")
print("  阶段2 (员工分类):     47.2ms/frame")
print("  总处理时间:           61.7ms/frame")
print()
print("  → 理论最大FPS: {:.1f} fps (1000ms / 61.7ms)".format(1000/61.7))
print("  → 实际处理FPS: 16.19 fps (包含视频读写开销)")
print()

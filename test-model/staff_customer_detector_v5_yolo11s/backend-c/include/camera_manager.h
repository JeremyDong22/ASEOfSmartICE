#ifndef SMARTICE_CAMERA_MANAGER_H
#define SMARTICE_CAMERA_MANAGER_H

#include "video_decoder.h"
#include "inference_engine.h"
#include <string>
#include <map>
#include <memory>
#include <mutex>
#include <opencv2/opencv.hpp>

namespace smartice {

// Camera statistics
struct CameraStats {
    int channel;
    std::string rtsp_url;
    bool is_running;
    int width;
    int height;
    double fps;
    int total_frames;
    int staff_count;
    int customer_count;
    float avg_inference_ms;
    int64_t start_time_ms;
};

// Camera session
struct CameraSession {
    int channel;
    std::string rtsp_url;
    std::unique_ptr<VideoDecoder> decoder;
    cv::Mat latest_annotated_frame;
    std::mutex frame_mutex;
    CameraStats stats;
    int64_t last_frame_time_ms;
};

class CameraManager {
public:
    explicit CameraManager(std::shared_ptr<InferenceEngine> engine);
    ~CameraManager();

    // Start camera
    bool start_camera(int channel, const std::string& rtsp_url);

    // Stop camera
    bool stop_camera(int channel);

    // Get latest MJPEG frame
    bool get_mjpeg_frame(int channel, std::vector<uint8_t>& jpeg_data);

    // Get camera stats
    bool get_camera_stats(int channel, CameraStats& stats);

    // Get all camera stats
    std::vector<CameraStats> get_all_stats();

    // Check if camera is running
    bool is_camera_running(int channel);

private:
    std::shared_ptr<InferenceEngine> inference_engine_;
    std::map<int, std::unique_ptr<CameraSession>> sessions_;
    std::mutex sessions_mutex_;

    // Frame callback
    void on_frame_received(int channel, const cv::Mat& frame);

    // Draw detections on frame
    cv::Mat draw_detections(const cv::Mat& frame, const InferenceResult& result);
};

} // namespace smartice

#endif // SMARTICE_CAMERA_MANAGER_H

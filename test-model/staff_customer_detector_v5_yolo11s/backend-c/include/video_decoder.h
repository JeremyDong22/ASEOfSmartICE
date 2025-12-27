#ifndef SMARTICE_VIDEO_DECODER_H
#define SMARTICE_VIDEO_DECODER_H

#include <string>
#include <memory>
#include <functional>
#include <thread>
#include <atomic>
#include <opencv2/opencv.hpp>

namespace smartice {

// Frame callback function type
using FrameCallback = std::function<void(const cv::Mat&)>;

class VideoDecoder {
public:
    explicit VideoDecoder(const std::string& rtsp_url);
    ~VideoDecoder();

    // Start decoding (non-blocking)
    void start(FrameCallback callback);

    // Stop decoding
    void stop();

    // Check if decoder is running
    bool is_running() const { return running_; }

    // Get video properties
    int get_width() const { return width_; }
    int get_height() const { return height_; }
    double get_fps() const { return fps_; }

    // Get latest frame (for MJPEG streaming)
    bool get_latest_frame(cv::Mat& frame);

private:
    std::string rtsp_url_;
    std::atomic<bool> running_;
    int width_;
    int height_;
    double fps_;

    // Decoding thread
    std::unique_ptr<std::thread> decode_thread_;
    FrameCallback frame_callback_;

    // Latest frame for streaming
    cv::Mat latest_frame_;
    std::mutex frame_mutex_;

    // Implementation-specific data (FFmpeg context)
    struct Impl;
    std::unique_ptr<Impl> impl_;

    // Decoding loop
    void decode_loop();
};

} // namespace smartice

#endif // SMARTICE_VIDEO_DECODER_H

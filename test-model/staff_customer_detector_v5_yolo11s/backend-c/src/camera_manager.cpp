#include "camera_manager.h"
#include "utils.h"
#include <chrono>

namespace smartice {

CameraManager::CameraManager(std::shared_ptr<InferenceEngine> engine)
    : inference_engine_(engine)
{
    auto logger = get_logger();
    logger->info("CameraManager created");
}

CameraManager::~CameraManager() {
    auto logger = get_logger();
    logger->info("Stopping all cameras");

    std::lock_guard<std::mutex> lock(sessions_mutex_);
    for (auto& [channel, session] : sessions_) {
        if (session->decoder) {
            session->decoder->stop();
        }
    }
    sessions_.clear();
}

bool CameraManager::start_camera(int channel, const std::string& rtsp_url) {
    auto logger = get_logger();
    logger->info("Starting camera {} with URL: {}", channel, rtsp_url);

    std::lock_guard<std::mutex> lock(sessions_mutex_);

    // Check if camera already running
    if (sessions_.find(channel) != sessions_.end()) {
        logger->warn("Camera {} already running", channel);
        return false;
    }

    // Create new session
    auto session = std::make_unique<CameraSession>();
    session->channel = channel;
    session->rtsp_url = rtsp_url;
    session->stats.channel = channel;
    session->stats.rtsp_url = rtsp_url;
    session->stats.is_running = false;
    session->stats.total_frames = 0;
    session->stats.staff_count = 0;
    session->stats.customer_count = 0;
    session->stats.avg_inference_ms = 0.0f;
    session->stats.start_time_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    session->last_frame_time_ms = 0;

    // Create video decoder
    session->decoder = std::make_unique<VideoDecoder>(rtsp_url);

    // Start decoding with callback
    session->decoder->start([this, channel](const cv::Mat& frame) {
        this->on_frame_received(channel, frame);
    });

    // Wait for first frame to get video properties
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    session->stats.width = session->decoder->get_width();
    session->stats.height = session->decoder->get_height();
    session->stats.fps = session->decoder->get_fps();
    session->stats.is_running = session->decoder->is_running();

    sessions_[channel] = std::move(session);

    logger->info("Camera {} started successfully: {}x{} @ {:.2f} FPS",
                 channel, session->stats.width, session->stats.height, session->stats.fps);

    return true;
}

bool CameraManager::stop_camera(int channel) {
    auto logger = get_logger();
    logger->info("Stopping camera {}", channel);

    std::lock_guard<std::mutex> lock(sessions_mutex_);

    auto it = sessions_.find(channel);
    if (it == sessions_.end()) {
        logger->warn("Camera {} not found", channel);
        return false;
    }

    if (it->second->decoder) {
        it->second->decoder->stop();
    }

    sessions_.erase(it);
    logger->info("Camera {} stopped", channel);

    return true;
}

void CameraManager::on_frame_received(int channel, const cv::Mat& frame) {
    auto logger = get_logger();

    std::lock_guard<std::mutex> lock(sessions_mutex_);

    auto it = sessions_.find(channel);
    if (it == sessions_.end()) {
        return;
    }

    auto& session = it->second;

    // Update frame count
    session->stats.total_frames++;

    // Run inference (throttle to ~5 FPS for efficiency)
    int64_t now_ms = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();

    if (now_ms - session->last_frame_time_ms < 200) {  // 200ms = 5 FPS
        return;
    }

    session->last_frame_time_ms = now_ms;

    try {
        // Run inference
        InferenceResult result = inference_engine_->infer(frame);

        // Update stats
        session->stats.staff_count = result.staff_count;
        session->stats.customer_count = result.customer_count;

        // Running average of inference time
        if (session->stats.avg_inference_ms == 0.0f) {
            session->stats.avg_inference_ms = result.inference_time_ms;
        } else {
            session->stats.avg_inference_ms = 0.9f * session->stats.avg_inference_ms +
                                               0.1f * result.inference_time_ms;
        }

        // Draw detections
        cv::Mat annotated_frame = draw_detections(frame, result);

        // Store annotated frame
        {
            std::lock_guard<std::mutex> frame_lock(session->frame_mutex);
            session->latest_annotated_frame = annotated_frame;
        }

        logger->debug("Camera {}: Staff={}, Customer={}, Inference={:.1f}ms",
                      channel, result.staff_count, result.customer_count,
                      result.inference_time_ms);

    } catch (const std::exception& e) {
        logger->error("Error processing frame for camera {}: {}", channel, e.what());
    }
}

cv::Mat CameraManager::draw_detections(const cv::Mat& frame, const InferenceResult& result) {
    cv::Mat annotated = frame.clone();

    for (const auto& det : result.detections) {
        // Choose color: Green for staff, Red for customer
        cv::Scalar color = (det.class_id == 0) ? cv::Scalar(0, 255, 0) : cv::Scalar(0, 0, 255);

        // Draw bounding box
        cv::rectangle(annotated,
                      cv::Point(static_cast<int>(det.x1), static_cast<int>(det.y1)),
                      cv::Point(static_cast<int>(det.x2), static_cast<int>(det.y2)),
                      color, 2);

        // Draw label with confidence
        std::string label = det.class_name + ": " +
                            std::to_string(static_cast<int>(det.confidence * 100)) + "%";

        int baseline = 0;
        cv::Size text_size = cv::getTextSize(label, cv::FONT_HERSHEY_SIMPLEX, 0.5, 1, &baseline);

        // Draw background for text
        cv::rectangle(annotated,
                      cv::Point(static_cast<int>(det.x1), static_cast<int>(det.y1) - text_size.height - 5),
                      cv::Point(static_cast<int>(det.x1) + text_size.width, static_cast<int>(det.y1)),
                      color, -1);

        // Draw text
        cv::putText(annotated, label,
                    cv::Point(static_cast<int>(det.x1), static_cast<int>(det.y1) - 5),
                    cv::FONT_HERSHEY_SIMPLEX, 0.5, cv::Scalar(255, 255, 255), 1);
    }

    // Draw stats overlay
    std::string stats_text = "Staff: " + std::to_string(result.staff_count) +
                             " | Customer: " + std::to_string(result.customer_count) +
                             " | " + std::to_string(static_cast<int>(result.inference_time_ms)) + "ms";

    cv::putText(annotated, stats_text,
                cv::Point(10, 30),
                cv::FONT_HERSHEY_SIMPLEX, 0.7, cv::Scalar(255, 255, 255), 2);

    return annotated;
}

bool CameraManager::get_mjpeg_frame(int channel, std::vector<uint8_t>& jpeg_data) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);

    auto it = sessions_.find(channel);
    if (it == sessions_.end()) {
        return false;
    }

    auto& session = it->second;

    cv::Mat frame;
    {
        std::lock_guard<std::mutex> frame_lock(session->frame_mutex);
        if (session->latest_annotated_frame.empty()) {
            return false;
        }
        frame = session->latest_annotated_frame.clone();
    }

    // Encode to JPEG
    std::vector<int> params = {cv::IMWRITE_JPEG_QUALITY, 85};
    cv::imencode(".jpg", frame, jpeg_data, params);

    return true;
}

bool CameraManager::get_camera_stats(int channel, CameraStats& stats) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);

    auto it = sessions_.find(channel);
    if (it == sessions_.end()) {
        return false;
    }

    stats = it->second->stats;
    stats.is_running = it->second->decoder->is_running();

    return true;
}

std::vector<CameraStats> CameraManager::get_all_stats() {
    std::lock_guard<std::mutex> lock(sessions_mutex_);

    std::vector<CameraStats> all_stats;
    all_stats.reserve(sessions_.size());

    for (const auto& [channel, session] : sessions_) {
        CameraStats stats = session->stats;
        stats.is_running = session->decoder->is_running();
        all_stats.push_back(stats);
    }

    return all_stats;
}

bool CameraManager::is_camera_running(int channel) {
    std::lock_guard<std::mutex> lock(sessions_mutex_);

    auto it = sessions_.find(channel);
    if (it == sessions_.end()) {
        return false;
    }

    return it->second->decoder->is_running();
}

} // namespace smartice

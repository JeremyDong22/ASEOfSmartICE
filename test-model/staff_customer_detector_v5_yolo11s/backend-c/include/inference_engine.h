#ifndef SMARTICE_INFERENCE_ENGINE_H
#define SMARTICE_INFERENCE_ENGINE_H

#include <string>
#include <vector>
#include <memory>
#include <opencv2/opencv.hpp>

namespace smartice {

// Detection result
struct Detection {
    float x1, y1, x2, y2;  // Bounding box
    float confidence;       // Detection confidence
    int class_id;          // Class ID (0=staff, 1=customer)
    std::string class_name;
};

// Inference result
struct InferenceResult {
    std::vector<Detection> detections;
    float inference_time_ms;
    int staff_count;
    int customer_count;
};

class InferenceEngine {
public:
    explicit InferenceEngine(const std::string& model_path, bool use_cuda = true);
    ~InferenceEngine();

    // Run inference on image data (raw RGB buffer)
    InferenceResult infer(const uint8_t* image_data, int width, int height);

    // Run inference on cv::Mat
    InferenceResult infer(const cv::Mat& image);

    // Batch inference
    std::vector<InferenceResult> infer_batch(const std::vector<cv::Mat>& images);

    // Check if engine is initialized
    bool is_initialized() const { return initialized_; }

    // Get model properties
    int get_input_width() const { return input_width_; }
    int get_input_height() const { return input_height_; }

    // Set confidence threshold
    void set_conf_threshold(float threshold) { conf_threshold_ = threshold; }
    void set_iou_threshold(float threshold) { iou_threshold_ = threshold; }

private:
    std::string model_path_;
    bool initialized_;
    bool use_cuda_;
    int input_width_;
    int input_height_;
    float conf_threshold_;
    float iou_threshold_;

    // Implementation-specific data (libtorch)
    struct Impl;
    std::unique_ptr<Impl> impl_;

    // Helper methods
    cv::Mat preprocess(const cv::Mat& image);
    std::vector<Detection> postprocess(const std::vector<float>& output, int orig_width, int orig_height);
    std::vector<Detection> non_max_suppression(std::vector<Detection>& detections);
};

} // namespace smartice

#endif // SMARTICE_INFERENCE_ENGINE_H

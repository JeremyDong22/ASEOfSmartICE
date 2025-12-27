#include "inference_engine.h"
#include "utils.h"
#include <torch/torch.h>
#include <torch/script.h>
#include <chrono>
#include <algorithm>

namespace smartice {

struct InferenceEngine::Impl {
    torch::jit::script::Module model;
    torch::Device device;

    Impl(torch::DeviceType device_type) : device(device_type) {}
};

InferenceEngine::InferenceEngine(const std::string& model_path, bool use_cuda)
    : model_path_(model_path)
    , initialized_(false)
    , use_cuda_(use_cuda)
    , input_width_(800)   // YOLO11s trained with 800x800
    , input_height_(800)
    , conf_threshold_(0.25)
    , iou_threshold_(0.45)
    , impl_(nullptr)
{
    auto logger = get_logger();
    logger->info("Loading YOLO11s model from: {}", model_path);

    try {
        // Determine device
        torch::DeviceType device_type = torch::kCPU;
        if (use_cuda_ && torch::cuda::is_available()) {
            device_type = torch::kCUDA;
            logger->info("Using CUDA device for inference");
        } else {
            logger->info("Using CPU for inference");
            use_cuda_ = false;
        }

        impl_ = std::make_unique<Impl>(device_type);

        // Load the model
        impl_->model = torch::jit::load(model_path);
        impl_->model.to(impl_->device);
        impl_->model.eval();

        initialized_ = true;
        logger->info("Model loaded successfully");
        logger->info("Input size: {}x{}", input_width_, input_height_);
        logger->info("Confidence threshold: {}", conf_threshold_);
        logger->info("IOU threshold: {}", iou_threshold_);

    } catch (const c10::Error& e) {
        logger->error("Error loading model: {}", e.what());
        initialized_ = false;
    }
}

InferenceEngine::~InferenceEngine() {
    auto logger = get_logger();
    if (initialized_) {
        logger->info("Destroying InferenceEngine");
    }
}

cv::Mat InferenceEngine::preprocess(const cv::Mat& image) {
    cv::Mat rgb_image;
    if (image.channels() == 3) {
        cv::cvtColor(image, rgb_image, cv::COLOR_BGR2RGB);
    } else {
        rgb_image = image.clone();
    }

    // Resize to model input size
    cv::Mat resized;
    cv::resize(rgb_image, resized, cv::Size(input_width_, input_height_));

    // Convert to float and normalize [0, 1]
    cv::Mat float_image;
    resized.convertTo(float_image, CV_32FC3, 1.0 / 255.0);

    return float_image;
}

std::vector<Detection> InferenceEngine::non_max_suppression(std::vector<Detection>& detections) {
    if (detections.empty()) {
        return detections;
    }

    // Sort by confidence (descending)
    std::sort(detections.begin(), detections.end(),
              [](const Detection& a, const Detection& b) {
                  return a.confidence > b.confidence;
              });

    std::vector<Detection> result;
    std::vector<bool> suppressed(detections.size(), false);

    for (size_t i = 0; i < detections.size(); ++i) {
        if (suppressed[i]) continue;

        result.push_back(detections[i]);

        // Calculate IoU with remaining boxes
        float area_i = (detections[i].x2 - detections[i].x1) * (detections[i].y2 - detections[i].y1);

        for (size_t j = i + 1; j < detections.size(); ++j) {
            if (suppressed[j]) continue;

            // Same class only
            if (detections[i].class_id != detections[j].class_id) continue;

            // Calculate intersection
            float xx1 = std::max(detections[i].x1, detections[j].x1);
            float yy1 = std::max(detections[i].y1, detections[j].y1);
            float xx2 = std::min(detections[i].x2, detections[j].x2);
            float yy2 = std::min(detections[i].y2, detections[j].y2);

            float w = std::max(0.0f, xx2 - xx1);
            float h = std::max(0.0f, yy2 - yy1);
            float intersection = w * h;

            float area_j = (detections[j].x2 - detections[j].x1) * (detections[j].y2 - detections[j].y1);
            float iou = intersection / (area_i + area_j - intersection);

            if (iou > iou_threshold_) {
                suppressed[j] = true;
            }
        }
    }

    return result;
}

std::vector<Detection> InferenceEngine::postprocess(const std::vector<float>& output,
                                                     int orig_width, int orig_height) {
    std::vector<Detection> detections;

    // YOLO11 output format: [batch, num_detections, 6]
    // Each detection: [x1, y1, x2, y2, confidence, class_id]
    int num_detections = output.size() / 6;

    float scale_x = static_cast<float>(orig_width) / input_width_;
    float scale_y = static_cast<float>(orig_height) / input_height_;

    for (int i = 0; i < num_detections; ++i) {
        int idx = i * 6;
        float confidence = output[idx + 4];

        if (confidence < conf_threshold_) {
            continue;
        }

        Detection det;
        det.x1 = output[idx + 0] * scale_x;
        det.y1 = output[idx + 1] * scale_y;
        det.x2 = output[idx + 2] * scale_x;
        det.y2 = output[idx + 3] * scale_y;
        det.confidence = confidence;
        det.class_id = static_cast<int>(output[idx + 5]);
        det.class_name = (det.class_id == 0) ? "staff" : "customer";

        detections.push_back(det);
    }

    // Apply NMS
    detections = non_max_suppression(detections);

    return detections;
}

InferenceResult InferenceEngine::infer(const cv::Mat& image) {
    auto logger = get_logger();
    InferenceResult result;
    result.inference_time_ms = 0.0f;
    result.staff_count = 0;
    result.customer_count = 0;

    if (!initialized_) {
        logger->error("Cannot run inference: Engine not initialized");
        return result;
    }

    auto start = std::chrono::high_resolution_clock::now();

    try {
        // Preprocess
        cv::Mat preprocessed = preprocess(image);

        // Convert to tensor [1, 3, H, W]
        torch::Tensor tensor = torch::from_blob(
            preprocessed.data,
            {1, input_height_, input_width_, 3},
            torch::kFloat32
        ).to(impl_->device);

        // Permute to [1, 3, H, W]
        tensor = tensor.permute({0, 3, 1, 2});

        // Run inference
        std::vector<torch::jit::IValue> inputs;
        inputs.push_back(tensor);

        torch::NoGradGuard no_grad;
        auto output = impl_->model.forward(inputs).toTensor();

        // Convert output to vector
        output = output.to(torch::kCPU);
        std::vector<float> output_vec(output.data_ptr<float>(),
                                       output.data_ptr<float>() + output.numel());

        // Postprocess
        result.detections = postprocess(output_vec, image.cols, image.rows);

        // Count staff and customers
        for (const auto& det : result.detections) {
            if (det.class_id == 0) {
                result.staff_count++;
            } else {
                result.customer_count++;
            }
        }

    } catch (const c10::Error& e) {
        logger->error("Inference error: {}", e.what());
    }

    auto end = std::chrono::high_resolution_clock::now();
    result.inference_time_ms = std::chrono::duration<float, std::milli>(end - start).count();

    logger->debug("Inference: {:.2f}ms, Staff: {}, Customer: {}",
                  result.inference_time_ms, result.staff_count, result.customer_count);

    return result;
}

InferenceResult InferenceEngine::infer(const uint8_t* image_data, int width, int height) {
    cv::Mat image(height, width, CV_8UC3, const_cast<uint8_t*>(image_data));
    return infer(image);
}

std::vector<InferenceResult> InferenceEngine::infer_batch(const std::vector<cv::Mat>& images) {
    std::vector<InferenceResult> results;
    results.reserve(images.size());

    // For now, process sequentially
    // TODO: Implement true batch inference
    for (const auto& image : images) {
        results.push_back(infer(image));
    }

    return results;
}

} // namespace smartice

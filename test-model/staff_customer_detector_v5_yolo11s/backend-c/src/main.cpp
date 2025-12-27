#include "http_server.h"
#include "camera_manager.h"
#include "inference_engine.h"
#include "thread_pool.h"
#include "utils.h"
#include <nlohmann/json.hpp>
#include <csignal>
#include <atomic>
#include <fstream>

using json = nlohmann::json;

std::atomic<bool> g_running(true);

void signal_handler(int signal) {
    if (signal == SIGINT || signal == SIGTERM) {
        smartice::get_logger()->info("Received signal {}, shutting down...", signal);
        g_running = false;
    }
}

// Helper to format RTSP URL
std::string get_rtsp_url(int channel) {
    return "rtsp://admin:ybl123456789@192.168.1.3:554/unicast/c" +
           std::to_string(channel) + "/s0/live";
}

int main(int argc, char* argv[]) {
    // Initialize logging
    smartice::init_logging("smartice_backend.log");
    auto logger = smartice::get_logger();

    logger->info("==============================================");
    logger->info("SmartICE C++ Backend Server v1.0.0");
    logger->info("YOLO11s Staff/Customer Detection");
    logger->info("==============================================");

    // Register signal handlers
    std::signal(SIGINT, signal_handler);
    std::signal(SIGTERM, signal_handler);

    // Parse command line arguments
    int port = 8001;
    std::string model_path = "../models/staff_customer_detector.pt";

    if (argc > 1) {
        port = std::stoi(argv[1]);
    }
    if (argc > 2) {
        model_path = argv[2];
    }

    logger->info("Configuration:");
    logger->info("  Port: {}", port);
    logger->info("  Model: {}", model_path);

    // Check if model exists
    std::ifstream model_file(model_path);
    if (!model_file.good()) {
        logger->error("Model file not found: {}", model_path);
        logger->error("Please ensure the .pt model file exists");
        return 1;
    }

    // Load YOLO model
    logger->info("Loading YOLO11s model...");
    auto inference_engine = std::make_shared<smartice::InferenceEngine>(model_path, true);

    if (!inference_engine->is_initialized()) {
        logger->error("Failed to initialize inference engine");
        return 1;
    }

    logger->info("Model loaded successfully");
    logger->info("  Input size: {}x{}", inference_engine->get_input_width(),
                 inference_engine->get_input_height());

    // Create camera manager
    auto camera_manager = std::make_shared<smartice::CameraManager>(inference_engine);

    // Create thread pool
    size_t num_threads = std::thread::hardware_concurrency();
    logger->info("Creating thread pool with {} threads", num_threads);
    smartice::ThreadPool thread_pool(num_threads);

    // Create HTTP server
    smartice::HttpServer server(port);

    // ============================================================================
    // API Routes
    // ============================================================================

    // Root endpoint
    server.add_route("GET", "/", [](const smartice::HttpRequest&) {
        smartice::HttpResponse response;
        response.status_code = 200;
        response.body = "SmartICE C++ Backend - YOLO11s Staff/Customer Detector\n"
                        "API Endpoints:\n"
                        "  POST /api/camera/start  - Start camera\n"
                        "  POST /api/camera/stop   - Stop camera\n"
                        "  GET  /api/stats         - Get all camera stats\n"
                        "  GET  /api/health        - Health check\n"
                        "  GET  /stream/mjpeg/{ch} - MJPEG stream\n";
        response.content_type = "text/plain";
        return response;
    });

    // Health check
    server.add_route("GET", "/api/health", [&inference_engine](const smartice::HttpRequest&) {
        json health_data = {
            {"status", "ok"},
            {"timestamp", smartice::get_current_time_string()},
            {"service", "SmartICE C++ Backend"},
            {"version", "1.0.0"},
            {"model", {
                {"loaded", inference_engine->is_initialized()},
                {"input_size", {
                    {"width", inference_engine->get_input_width()},
                    {"height", inference_engine->get_input_height()}
                }}
            }}
        };

        smartice::HttpResponse response;
        response.status_code = 200;
        response.body = health_data.dump(2);
        response.content_type = "application/json";
        return response;
    });

    // Start camera
    server.add_route("POST", "/api/camera/start", [&camera_manager](const smartice::HttpRequest& req) {
        auto logger = smartice::get_logger();

        try {
            json body = json::parse(req.body);
            int channel = body.value("channel", 0);

            if (channel <= 0 || channel > 30) {
                json error = {{"error", "Invalid channel (must be 1-30)"}};
                smartice::HttpResponse response;
                response.status_code = 400;
                response.body = error.dump();
                response.content_type = "application/json";
                return response;
            }

            std::string rtsp_url = get_rtsp_url(channel);
            bool success = camera_manager->start_camera(channel, rtsp_url);

            json result = {
                {"success", success},
                {"channel", channel},
                {"rtsp_url", rtsp_url},
                {"stream_url", "/stream/mjpeg/" + std::to_string(channel)}
            };

            smartice::HttpResponse response;
            response.status_code = success ? 200 : 500;
            response.body = result.dump(2);
            response.content_type = "application/json";
            return response;

        } catch (const std::exception& e) {
            logger->error("Error starting camera: {}", e.what());
            json error = {{"error", e.what()}};
            smartice::HttpResponse response;
            response.status_code = 500;
            response.body = error.dump();
            response.content_type = "application/json";
            return response;
        }
    });

    // Stop camera
    server.add_route("POST", "/api/camera/stop", [&camera_manager](const smartice::HttpRequest& req) {
        auto logger = smartice::get_logger();

        try {
            json body = json::parse(req.body);
            int channel = body.value("channel", 0);

            bool success = camera_manager->stop_camera(channel);

            json result = {
                {"success", success},
                {"channel", channel}
            };

            smartice::HttpResponse response;
            response.status_code = success ? 200 : 404;
            response.body = result.dump(2);
            response.content_type = "application/json";
            return response;

        } catch (const std::exception& e) {
            logger->error("Error stopping camera: {}", e.what());
            json error = {{"error", e.what()}};
            smartice::HttpResponse response;
            response.status_code = 500;
            response.body = error.dump();
            response.content_type = "application/json";
            return response;
        }
    });

    // Get stats
    server.add_route("GET", "/api/stats", [&camera_manager, &thread_pool](const smartice::HttpRequest&) {
        std::vector<smartice::CameraStats> all_stats = camera_manager->get_all_stats();

        json cameras = json::array();
        int total_staff = 0;
        int total_customer = 0;
        int total_frames = 0;

        for (const auto& stats : all_stats) {
            cameras.push_back({
                {"channel", stats.channel},
                {"rtsp_url", stats.rtsp_url},
                {"is_running", stats.is_running},
                {"width", stats.width},
                {"height", stats.height},
                {"fps", stats.fps},
                {"total_frames", stats.total_frames},
                {"staff_count", stats.staff_count},
                {"customer_count", stats.customer_count},
                {"avg_inference_ms", stats.avg_inference_ms}
            });

            total_staff += stats.staff_count;
            total_customer += stats.customer_count;
            total_frames += stats.total_frames;
        }

        json stats_data = {
            {"cameras", cameras},
            {"summary", {
                {"num_cameras", all_stats.size()},
                {"total_staff", total_staff},
                {"total_customer", total_customer},
                {"total_frames", total_frames}
            }},
            {"thread_pool", {
                {"num_threads", thread_pool.size()},
                {"pending_tasks", thread_pool.pending_tasks()}
            }},
            {"timestamp", smartice::get_current_time_string()}
        };

        smartice::HttpResponse response;
        response.status_code = 200;
        response.body = stats_data.dump(2);
        response.content_type = "application/json";
        return response;
    });

    // MJPEG stream (simplified - single frame response)
    server.add_route("GET", "/stream/mjpeg/18", [&camera_manager](const smartice::HttpRequest&) {
        auto logger = smartice::get_logger();
        std::vector<uint8_t> jpeg_data;

        if (camera_manager->get_mjpeg_frame(18, jpeg_data)) {
            smartice::HttpResponse response;
            response.status_code = 200;
            response.body = std::string(jpeg_data.begin(), jpeg_data.end());
            response.content_type = "image/jpeg";
            return response;
        }

        logger->warn("No frame available for camera 18");
        smartice::HttpResponse response;
        response.status_code = 404;
        response.body = "No frame available";
        response.content_type = "text/plain";
        return response;
    });

    // Start server in background thread
    std::thread server_thread([&server]() {
        server.start();
    });

    logger->info("Server started on http://localhost:{}", port);
    logger->info("");
    logger->info("Available endpoints:");
    logger->info("  GET  /              - API documentation");
    logger->info("  GET  /api/health    - Health check");
    logger->info("  POST /api/camera/start - Start camera (JSON: {{\"channel\": 18}})");
    logger->info("  POST /api/camera/stop  - Stop camera (JSON: {{\"channel\": 18}})");
    logger->info("  GET  /api/stats     - All camera statistics");
    logger->info("  GET  /stream/mjpeg/18 - MJPEG frame from camera 18");
    logger->info("");
    logger->info("Example commands:");
    logger->info("  curl -X POST http://localhost:{}/api/camera/start -d '{{\"channel\":18}}'", port);
    logger->info("  curl http://localhost:{}/api/stats", port);
    logger->info("  curl http://localhost:{}/stream/mjpeg/18 --output frame.jpg", port);
    logger->info("");
    logger->info("Press Ctrl+C to stop");

    // Wait for shutdown signal
    while (g_running) {
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }

    // Shutdown
    logger->info("Initiating graceful shutdown...");
    server.stop();

    if (server_thread.joinable()) {
        server_thread.join();
    }

    logger->info("Shutdown complete");
    return 0;
}

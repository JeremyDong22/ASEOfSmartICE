#include "utils.h"
#include <spdlog/sinks/stdout_color_sinks.h>
#include <spdlog/sinks/rotating_file_sink.h>
#include <chrono>
#include <iomanip>
#include <sstream>

namespace smartice {

static std::shared_ptr<spdlog::logger> g_logger;

void init_logging(const std::string& log_file) {
    try {
        // Create console sink
        auto console_sink = std::make_shared<spdlog::sinks::stdout_color_sink_mt>();
        console_sink->set_level(spdlog::level::info);

        // Create rotating file sink (10MB max, 3 files)
        auto file_sink = std::make_shared<spdlog::sinks::rotating_file_sink_mt>(
            log_file, 1024 * 1024 * 10, 3
        );
        file_sink->set_level(spdlog::level::debug);

        // Combine sinks
        std::vector<spdlog::sink_ptr> sinks{console_sink, file_sink};
        g_logger = std::make_shared<spdlog::logger>("smartice", sinks.begin(), sinks.end());

        // Set pattern
        g_logger->set_pattern("[%Y-%m-%d %H:%M:%S.%e] [%^%l%$] [%t] %v");
        g_logger->set_level(spdlog::level::debug);

        // Register as default logger
        spdlog::register_logger(g_logger);
        spdlog::set_default_logger(g_logger);

        g_logger->info("Logging initialized: {}", log_file);
    } catch (const spdlog::spdlog_ex& ex) {
        std::cerr << "Log initialization failed: " << ex.what() << std::endl;
    }
}

std::shared_ptr<spdlog::logger> get_logger() {
    if (!g_logger) {
        init_logging();
    }
    return g_logger;
}

std::string get_current_time_string() {
    auto now = std::chrono::system_clock::now();
    auto time_t = std::chrono::system_clock::to_time_t(now);
    std::stringstream ss;
    ss << std::put_time(std::localtime(&time_t), "%Y-%m-%d %H:%M:%S");
    return ss.str();
}

std::string format_bytes(size_t bytes) {
    const char* units[] = {"B", "KB", "MB", "GB", "TB"};
    int unit_index = 0;
    double size = static_cast<double>(bytes);

    while (size >= 1024.0 && unit_index < 4) {
        size /= 1024.0;
        unit_index++;
    }

    std::stringstream ss;
    ss << std::fixed << std::setprecision(2) << size << " " << units[unit_index];
    return ss.str();
}

} // namespace smartice

#ifndef SMARTICE_UTILS_H
#define SMARTICE_UTILS_H

#include <string>
#include <memory>
#include <spdlog/spdlog.h>

namespace smartice {

// Initialize logging system
void init_logging(const std::string& log_file = "smartice_backend.log");

// Get shared logger instance
std::shared_ptr<spdlog::logger> get_logger();

// Utility functions
std::string get_current_time_string();
std::string format_bytes(size_t bytes);

} // namespace smartice

#endif // SMARTICE_UTILS_H

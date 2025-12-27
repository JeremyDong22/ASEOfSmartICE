#include "http_server.h"
#include "utils.h"
#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <thread>
#include <sstream>
#include <cstring>

namespace smartice {

struct HttpServer::Impl {
    int server_fd = -1;
    std::thread server_thread;
};

HttpServer::HttpServer(int port)
    : port_(port)
    , running_(false)
    , impl_(std::make_unique<Impl>())
{
    auto logger = get_logger();
    logger->info("HTTP Server created on port {}", port);
}

HttpServer::~HttpServer() {
    if (running_) {
        stop();
    }
}

void HttpServer::add_route(const std::string& method, const std::string& path, RequestHandler handler) {
    std::string key = method + " " + path;
    routes_[key] = handler;
    get_logger()->debug("Registered route: {}", key);
}

HttpResponse HttpServer::handle_request(const HttpRequest& request) {
    std::string key = request.method + " " + request.path;
    auto it = routes_.find(key);

    if (it != routes_.end()) {
        return it->second(request);
    }

    // Default 404 response
    HttpResponse response;
    response.status_code = 404;
    response.body = "404 Not Found";
    response.content_type = "text/plain";
    return response;
}

void HttpServer::start() {
    auto logger = get_logger();

    // Create socket
    impl_->server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (impl_->server_fd < 0) {
        logger->error("Failed to create socket");
        return;
    }

    // Set socket options
    int opt = 1;
    if (setsockopt(impl_->server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt)) < 0) {
        logger->error("Failed to set socket options");
        close(impl_->server_fd);
        return;
    }

    // Bind socket
    struct sockaddr_in address;
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(port_);

    if (bind(impl_->server_fd, (struct sockaddr*)&address, sizeof(address)) < 0) {
        logger->error("Failed to bind socket to port {}", port_);
        close(impl_->server_fd);
        return;
    }

    // Listen
    if (listen(impl_->server_fd, 10) < 0) {
        logger->error("Failed to listen on socket");
        close(impl_->server_fd);
        return;
    }

    running_ = true;
    logger->info("HTTP Server listening on port {}", port_);

    // Accept loop
    while (running_) {
        struct sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);

        int client_fd = accept(impl_->server_fd, (struct sockaddr*)&client_addr, &client_len);
        if (client_fd < 0) {
            if (running_) {
                logger->error("Failed to accept connection");
            }
            continue;
        }

        // Read request
        char buffer[4096] = {0};
        ssize_t bytes_read = read(client_fd, buffer, sizeof(buffer) - 1);

        if (bytes_read > 0) {
            // Parse HTTP request (simple parser)
            std::string request_str(buffer, bytes_read);
            std::istringstream iss(request_str);

            HttpRequest request;
            std::string first_line;
            std::getline(iss, first_line);

            // Parse method and path
            std::istringstream line_stream(first_line);
            line_stream >> request.method >> request.path;

            // Handle request
            HttpResponse response = handle_request(request);

            // Build HTTP response
            std::ostringstream response_stream;
            response_stream << "HTTP/1.1 " << response.status_code << " OK\r\n";
            response_stream << "Content-Type: " << response.content_type << "\r\n";
            response_stream << "Content-Length: " << response.body.length() << "\r\n";
            response_stream << "Connection: close\r\n";
            response_stream << "\r\n";
            response_stream << response.body;

            std::string response_str = response_stream.str();
            write(client_fd, response_str.c_str(), response_str.length());

            logger->debug("Handled {} {} -> {}", request.method, request.path, response.status_code);
        }

        close(client_fd);
    }

    close(impl_->server_fd);
    logger->info("HTTP Server stopped");
}

void HttpServer::stop() {
    if (running_) {
        running_ = false;
        if (impl_->server_fd >= 0) {
            shutdown(impl_->server_fd, SHUT_RDWR);
        }
        get_logger()->info("Stopping HTTP server");
    }
}

} // namespace smartice

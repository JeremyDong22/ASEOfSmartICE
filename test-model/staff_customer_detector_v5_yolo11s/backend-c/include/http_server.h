#ifndef SMARTICE_HTTP_SERVER_H
#define SMARTICE_HTTP_SERVER_H

#include <string>
#include <functional>
#include <map>
#include <memory>

namespace smartice {

// HTTP request structure
struct HttpRequest {
    std::string method;     // GET, POST, etc.
    std::string path;       // /api/health
    std::string body;       // Request body
    std::map<std::string, std::string> headers;
};

// HTTP response structure
struct HttpResponse {
    int status_code = 200;
    std::string body;
    std::string content_type = "text/plain";
};

// Request handler function type
using RequestHandler = std::function<HttpResponse(const HttpRequest&)>;

class HttpServer {
public:
    explicit HttpServer(int port = 8001);
    ~HttpServer();

    // Register route handler
    void add_route(const std::string& method, const std::string& path, RequestHandler handler);

    // Start server (blocking)
    void start();

    // Stop server
    void stop();

    // Check if server is running
    bool is_running() const { return running_; }

private:
    int port_;
    bool running_;
    std::map<std::string, RequestHandler> routes_;

    // Implementation-specific data
    struct Impl;
    std::unique_ptr<Impl> impl_;

    // Internal handler dispatch
    HttpResponse handle_request(const HttpRequest& request);
};

} // namespace smartice

#endif // SMARTICE_HTTP_SERVER_H

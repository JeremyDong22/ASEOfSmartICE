#include "http_server.h"
#include "utils.h"
#include <thread>
#include <chrono>
#include <iostream>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>

bool send_http_request(int port, const std::string& path, std::string& response) {
    int sock = socket(AF_INET, SOCK_STREAM, 0);
    if (sock < 0) {
        return false;
    }

    struct sockaddr_in server_addr;
    server_addr.sin_family = AF_INET;
    server_addr.sin_port = htons(port);
    inet_pton(AF_INET, "127.0.0.1", &server_addr.sin_addr);

    if (connect(sock, (struct sockaddr*)&server_addr, sizeof(server_addr)) < 0) {
        close(sock);
        return false;
    }

    std::string request = "GET " + path + " HTTP/1.1\r\nHost: localhost\r\n\r\n";
    send(sock, request.c_str(), request.length(), 0);

    char buffer[4096] = {0};
    ssize_t bytes = recv(sock, buffer, sizeof(buffer) - 1, 0);
    if (bytes > 0) {
        response = std::string(buffer, bytes);
    }

    close(sock);
    return bytes > 0;
}

int main() {
    smartice::init_logging("test_http_server.log");
    auto logger = smartice::get_logger();

    logger->info("Starting HTTP server test");

    // Create server
    int test_port = 8901;
    smartice::HttpServer server(test_port);

    // Register test route
    server.add_route("GET", "/test", [](const smartice::HttpRequest&) {
        smartice::HttpResponse response;
        response.body = "test_ok";
        return response;
    });

    // Start server in background
    std::thread server_thread([&server]() {
        server.start();
    });

    // Wait for server to start
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    // Test 1: Send request to /test
    logger->info("Test 1: Sending GET request to /test");
    std::string response;
    bool success = send_http_request(test_port, "/test", response);

    if (success && response.find("test_ok") != std::string::npos) {
        logger->info("Test 1: PASSED");
        std::cout << "Test 1: PASSED - Got expected response" << std::endl;
    } else {
        logger->error("Test 1: FAILED");
        std::cerr << "Test 1: FAILED - Response: " << response << std::endl;
        server.stop();
        if (server_thread.joinable()) server_thread.join();
        return 1;
    }

    // Test 2: 404 for non-existent route
    logger->info("Test 2: Sending GET request to /nonexistent");
    success = send_http_request(test_port, "/nonexistent", response);

    if (success && response.find("404") != std::string::npos) {
        logger->info("Test 2: PASSED");
        std::cout << "Test 2: PASSED - Got 404 as expected" << std::endl;
    } else {
        logger->error("Test 2: FAILED");
        std::cerr << "Test 2: FAILED - Response: " << response << std::endl;
        server.stop();
        if (server_thread.joinable()) server_thread.join();
        return 1;
    }

    // Stop server
    logger->info("Stopping server");
    server.stop();
    if (server_thread.joinable()) {
        server_thread.join();
    }

    logger->info("All tests passed!");
    std::cout << "\nAll HTTP server tests passed!" << std::endl;
    return 0;
}

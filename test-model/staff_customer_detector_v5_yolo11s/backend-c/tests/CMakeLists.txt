cmake_minimum_required(VERSION 3.18)

# Test executables
add_executable(test_http_server test_http_server.cpp)
target_link_libraries(test_http_server PRIVATE smartice_backend)

add_executable(test_thread_pool test_thread_pool.cpp)
target_link_libraries(test_thread_pool PRIVATE smartice_backend)

add_executable(test_lockfree_queue test_lockfree_queue.cpp)
target_link_libraries(test_lockfree_queue PRIVATE smartice_backend)

# Register tests with CTest
add_test(NAME HttpServerTest COMMAND test_http_server)
add_test(NAME ThreadPoolTest COMMAND test_thread_pool)
add_test(NAME LockFreeQueueTest COMMAND test_lockfree_queue)

# Set test properties
set_tests_properties(HttpServerTest PROPERTIES TIMEOUT 10)
set_tests_properties(ThreadPoolTest PROPERTIES TIMEOUT 10)
set_tests_properties(LockFreeQueueTest PROPERTIES TIMEOUT 10)

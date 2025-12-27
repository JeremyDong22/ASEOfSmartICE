#include "thread_pool.h"
#include "utils.h"
#include <atomic>
#include <iostream>
#include <vector>

int main() {
    smartice::init_logging("test_thread_pool.log");
    auto logger = smartice::get_logger();

    logger->info("Starting thread pool test");

    // Test 1: Basic task execution
    logger->info("Test 1: Basic task execution");
    {
        smartice::ThreadPool pool(4);
        std::atomic<int> counter(0);

        for (int i = 0; i < 100; ++i) {
            pool.enqueue([&counter]() {
                counter++;
            });
        }

        // Wait a bit for tasks to complete
        std::this_thread::sleep_for(std::chrono::milliseconds(500));

        if (counter == 100) {
            logger->info("Test 1: PASSED");
            std::cout << "Test 1: PASSED - All 100 tasks completed" << std::endl;
        } else {
            logger->error("Test 1: FAILED - Expected 100, got {}", counter.load());
            std::cerr << "Test 1: FAILED - Expected 100, got " << counter.load() << std::endl;
            return 1;
        }
    }

    // Test 2: Task with return value
    logger->info("Test 2: Task with return value");
    {
        smartice::ThreadPool pool(2);

        auto future = pool.enqueue([]() {
            return 42;
        });

        int result = future.get();
        if (result == 42) {
            logger->info("Test 2: PASSED");
            std::cout << "Test 2: PASSED - Got expected return value 42" << std::endl;
        } else {
            logger->error("Test 2: FAILED - Expected 42, got {}", result);
            std::cerr << "Test 2: FAILED - Expected 42, got " << result << std::endl;
            return 1;
        }
    }

    // Test 3: Multiple tasks with futures
    logger->info("Test 3: Multiple tasks with futures");
    {
        smartice::ThreadPool pool(4);
        std::vector<std::future<int>> futures;

        for (int i = 0; i < 10; ++i) {
            futures.push_back(pool.enqueue([i]() {
                return i * i;
            }));
        }

        bool all_correct = true;
        for (int i = 0; i < 10; ++i) {
            int result = futures[i].get();
            if (result != i * i) {
                all_correct = false;
                logger->error("Test 3: Task {} returned {}, expected {}", i, result, i * i);
            }
        }

        if (all_correct) {
            logger->info("Test 3: PASSED");
            std::cout << "Test 3: PASSED - All futures returned correct values" << std::endl;
        } else {
            std::cerr << "Test 3: FAILED - Some futures returned incorrect values" << std::endl;
            return 1;
        }
    }

    logger->info("All tests passed!");
    std::cout << "\nAll thread pool tests passed!" << std::endl;
    return 0;
}

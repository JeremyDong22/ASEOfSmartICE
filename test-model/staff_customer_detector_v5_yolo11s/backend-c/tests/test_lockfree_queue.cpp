#include "lockfree_queue.hpp"
#include "utils.h"
#include <thread>
#include <vector>
#include <atomic>
#include <iostream>

int main() {
    smartice::init_logging("test_lockfree_queue.log");
    auto logger = smartice::get_logger();

    logger->info("Starting lock-free queue test");

    // Test 1: Basic push/pop
    logger->info("Test 1: Basic push/pop");
    {
        smartice::LockFreeQueue<int> queue;

        queue.push(1);
        queue.push(2);
        queue.push(3);

        int val;
        bool success = queue.pop(val);
        if (success && val == 1) {
            logger->info("Test 1a: PASSED - First pop returned 1");
            std::cout << "Test 1a: PASSED - First pop returned 1" << std::endl;
        } else {
            logger->error("Test 1a: FAILED - Expected 1, got {}", val);
            std::cerr << "Test 1a: FAILED" << std::endl;
            return 1;
        }

        success = queue.pop(val);
        if (success && val == 2) {
            logger->info("Test 1b: PASSED - Second pop returned 2");
            std::cout << "Test 1b: PASSED - Second pop returned 2" << std::endl;
        } else {
            logger->error("Test 1b: FAILED - Expected 2, got {}", val);
            std::cerr << "Test 1b: FAILED" << std::endl;
            return 1;
        }
    }

    // Test 2: Empty queue
    logger->info("Test 2: Empty queue");
    {
        smartice::LockFreeQueue<int> queue;
        int val;
        bool success = queue.pop(val);

        if (!success && queue.empty()) {
            logger->info("Test 2: PASSED - Pop from empty queue returns false");
            std::cout << "Test 2: PASSED - Empty queue behavior correct" << std::endl;
        } else {
            logger->error("Test 2: FAILED");
            std::cerr << "Test 2: FAILED" << std::endl;
            return 1;
        }
    }

    // Test 3: Multi-threaded stress test
    logger->info("Test 3: Multi-threaded stress test");
    {
        smartice::LockFreeQueue<int> queue;
        const int num_producers = 4;
        const int num_consumers = 4;
        const int items_per_producer = 1000;
        std::atomic<int> total_consumed(0);

        // Producer threads
        std::vector<std::thread> producers;
        for (int i = 0; i < num_producers; ++i) {
            producers.emplace_back([&queue, items_per_producer]() {
                for (int j = 0; j < items_per_producer; ++j) {
                    queue.push(j);
                }
            });
        }

        // Consumer threads
        std::vector<std::thread> consumers;
        std::atomic<bool> done(false);
        for (int i = 0; i < num_consumers; ++i) {
            consumers.emplace_back([&queue, &total_consumed, &done]() {
                int val;
                while (!done || !queue.empty()) {
                    if (queue.pop(val)) {
                        total_consumed++;
                    } else {
                        std::this_thread::yield();
                    }
                }
            });
        }

        // Wait for producers
        for (auto& t : producers) {
            t.join();
        }

        // Wait a bit for consumers to catch up
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
        done = true;

        // Wait for consumers
        for (auto& t : consumers) {
            t.join();
        }

        int expected = num_producers * items_per_producer;
        if (total_consumed == expected) {
            logger->info("Test 3: PASSED - Consumed {} items", total_consumed.load());
            std::cout << "Test 3: PASSED - Multi-threaded stress test successful" << std::endl;
        } else {
            logger->error("Test 3: FAILED - Expected {}, consumed {}", expected, total_consumed.load());
            std::cerr << "Test 3: FAILED - Expected " << expected << ", consumed " << total_consumed.load() << std::endl;
            return 1;
        }
    }

    logger->info("All tests passed!");
    std::cout << "\nAll lock-free queue tests passed!" << std::endl;
    return 0;
}

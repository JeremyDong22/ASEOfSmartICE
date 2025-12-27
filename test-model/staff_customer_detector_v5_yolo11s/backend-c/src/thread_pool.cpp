#include "thread_pool.h"
#include "utils.h"

namespace smartice {

ThreadPool::ThreadPool(size_t num_threads)
    : stop_(false)
{
    auto logger = get_logger();
    logger->info("Initializing thread pool with {} threads", num_threads);

    for (size_t i = 0; i < num_threads; ++i) {
        workers_.emplace_back([this, i] {
            auto logger = get_logger();
            logger->debug("Worker thread {} started", i);

            while (true) {
                std::function<void()> task;

                {
                    std::unique_lock<std::mutex> lock(queue_mutex_);
                    condition_.wait(lock, [this] {
                        return stop_ || !tasks_.empty();
                    });

                    if (stop_ && tasks_.empty()) {
                        logger->debug("Worker thread {} stopping", i);
                        return;
                    }

                    task = std::move(tasks_.front());
                    tasks_.pop();
                }

                try {
                    task();
                } catch (const std::exception& e) {
                    logger->error("Worker thread {} exception: {}", i, e.what());
                } catch (...) {
                    logger->error("Worker thread {} unknown exception", i);
                }
            }
        });
    }
}

ThreadPool::~ThreadPool() {
    auto logger = get_logger();
    logger->info("Shutting down thread pool");

    {
        std::unique_lock<std::mutex> lock(queue_mutex_);
        stop_ = true;
    }

    condition_.notify_all();

    for (std::thread& worker : workers_) {
        if (worker.joinable()) {
            worker.join();
        }
    }

    logger->info("Thread pool shutdown complete");
}

size_t ThreadPool::pending_tasks() const {
    std::unique_lock<std::mutex> lock(queue_mutex_);
    return tasks_.size();
}

} // namespace smartice

#ifndef SMARTICE_THREAD_POOL_H
#define SMARTICE_THREAD_POOL_H

#include <vector>
#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <functional>
#include <future>
#include <memory>
#include <stdexcept>

namespace smartice {

class ThreadPool {
public:
    // Constructor: create thread pool with specified number of threads
    explicit ThreadPool(size_t num_threads);

    // Destructor: stop all threads and wait for completion
    ~ThreadPool();

    // Enqueue a task and return a future
    template<typename F, typename... Args>
    auto enqueue(F&& f, Args&&... args)
        -> std::future<typename std::invoke_result<F, Args...>::type>;

    // Get number of threads
    size_t size() const { return workers_.size(); }

    // Get number of pending tasks
    size_t pending_tasks() const;

private:
    // Worker threads
    std::vector<std::thread> workers_;

    // Task queue
    std::queue<std::function<void()>> tasks_;

    // Synchronization
    mutable std::mutex queue_mutex_;
    std::condition_variable condition_;
    bool stop_;
};

// Template implementation
template<typename F, typename... Args>
auto ThreadPool::enqueue(F&& f, Args&&... args)
    -> std::future<typename std::invoke_result<F, Args...>::type>
{
    using return_type = typename std::invoke_result<F, Args...>::type;

    auto task = std::make_shared<std::packaged_task<return_type()>>(
        std::bind(std::forward<F>(f), std::forward<Args>(args)...)
    );

    std::future<return_type> result = task->get_future();

    {
        std::unique_lock<std::mutex> lock(queue_mutex_);

        if (stop_) {
            throw std::runtime_error("enqueue on stopped ThreadPool");
        }

        tasks_.emplace([task]() { (*task)(); });
    }

    condition_.notify_one();
    return result;
}

} // namespace smartice

#endif // SMARTICE_THREAD_POOL_H

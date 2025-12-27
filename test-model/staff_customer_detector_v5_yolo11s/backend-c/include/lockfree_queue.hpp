#ifndef SMARTICE_LOCKFREE_QUEUE_HPP
#define SMARTICE_LOCKFREE_QUEUE_HPP

#include <atomic>
#include <memory>

namespace smartice {

template<typename T>
class LockFreeQueue {
private:
    struct Node {
        std::shared_ptr<T> data;
        std::atomic<Node*> next;

        Node() : next(nullptr) {}
        explicit Node(T const& value) : data(std::make_shared<T>(value)), next(nullptr) {}
    };

    std::atomic<Node*> head_;
    std::atomic<Node*> tail_;
    std::atomic<size_t> size_;

public:
    LockFreeQueue() : size_(0) {
        Node* dummy = new Node();
        head_.store(dummy);
        tail_.store(dummy);
    }

    ~LockFreeQueue() {
        while (Node* old_head = head_.load()) {
            head_.store(old_head->next);
            delete old_head;
        }
    }

    // Disable copy
    LockFreeQueue(const LockFreeQueue&) = delete;
    LockFreeQueue& operator=(const LockFreeQueue&) = delete;

    // Push item to queue
    bool push(T const& value) {
        Node* new_node = new Node(value);
        Node* old_tail = tail_.load();

        while (true) {
            Node* tail_next = old_tail->next.load();

            // Check if tail is still the last node
            if (old_tail == tail_.load()) {
                if (tail_next == nullptr) {
                    // Try to link new node
                    if (old_tail->next.compare_exchange_weak(tail_next, new_node)) {
                        // Successfully added node, update tail
                        tail_.compare_exchange_weak(old_tail, new_node);
                        size_.fetch_add(1, std::memory_order_relaxed);
                        return true;
                    }
                } else {
                    // Tail was not pointing to last node, try to swing tail
                    tail_.compare_exchange_weak(old_tail, tail_next);
                }
            }
            old_tail = tail_.load();
        }
    }

    // Pop item from queue
    bool pop(T& result) {
        Node* old_head = head_.load();

        while (true) {
            Node* old_tail = tail_.load();
            Node* head_next = old_head->next.load();

            // Check if head is still valid
            if (old_head == head_.load()) {
                // Is queue empty?
                if (old_head == old_tail) {
                    if (head_next == nullptr) {
                        return false;  // Queue is empty
                    }
                    // Tail is falling behind, try to advance it
                    tail_.compare_exchange_weak(old_tail, head_next);
                } else {
                    // Read value before CAS, otherwise another dequeue might free the next node
                    if (head_next && head_next->data) {
                        result = *(head_next->data);
                        // Try to swing head to next node
                        if (head_.compare_exchange_weak(old_head, head_next)) {
                            delete old_head;
                            size_.fetch_sub(1, std::memory_order_relaxed);
                            return true;
                        }
                    } else {
                        return false;
                    }
                }
            }
            old_head = head_.load();
        }
    }

    // Get approximate size (may not be exact due to concurrent operations)
    size_t size() const {
        return size_.load(std::memory_order_relaxed);
    }

    // Check if queue is empty
    bool empty() const {
        Node* old_head = head_.load();
        Node* old_tail = tail_.load();
        Node* head_next = old_head->next.load();
        return (old_head == old_tail) && (head_next == nullptr);
    }
};

} // namespace smartice

#endif // SMARTICE_LOCKFREE_QUEUE_HPP

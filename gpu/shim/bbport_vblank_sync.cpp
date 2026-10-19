// SPDX-License-Identifier: GPL-2.0-or-later
// ufc4 (BB_VBLANK_SYNC=1): the display's vblank, seen through VK_KHR_present_wait.
//
// The port's virtual vblank runs on its own 60 Hz clock, with no relation to the display's
// refresh. A flip handed to the swapchain right at a display refresh is shown on that refresh
// or on the next one, depending on a fraction of a millisecond: frame times seen on screen
// jitter (21-45 ms at 30 FPS under gamescope) although the port flips every 33.3 ms. A thread
// here waits for each presented frame to reach the screen and records when; the present thread
// (videoout/driver.cpp) moves its vblank ticks to a fixed phase after those times.
#include "bbport_vblank_sync.h"

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <mutex>
#include <thread>

namespace BbVblankSync {
namespace {

std::mutex mutex;
std::condition_variable changed;
vk::Device pending_device;
vk::SwapchainKHR pending_swapchain;
std::uint64_t pending_id = 0;
vk::SwapchainKHR waiting_on; // the swapchain the thread is waiting on, if any
std::atomic<std::int64_t> last_scanout{0};
std::once_flag started;

std::int64_t Now() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
               std::chrono::steady_clock::now().time_since_epoch())
        .count();
}

void Run() {
    for (;;) {
        vk::Device device;
        vk::SwapchainKHR swapchain;
        std::uint64_t id;
        {
            std::unique_lock lk{mutex};
            changed.wait(lk, [] { return pending_id != 0; });
            device = pending_device;
            swapchain = pending_swapchain;
            id = pending_id; // only the latest frame: older ones are on screen already
            pending_id = 0;
            waiting_on = swapchain;
        }
        // 100 ms bound: a swapchain being destroyed waits for this call (Forget).
        const vk::Result result = device.waitForPresentKHR(swapchain, id, 100'000'000);
        const std::int64_t now = Now();
        {
            std::scoped_lock lk{mutex};
            waiting_on = nullptr;
        }
        changed.notify_all();
        if (result == vk::Result::eSuccess) {
            last_scanout.store(now, std::memory_order_relaxed);
        }
    }
}

} // namespace

void Presented(vk::Device device, vk::SwapchainKHR swapchain, std::uint64_t id) {
    std::call_once(started, [] { std::thread(Run).detach(); });
    {
        std::scoped_lock lk{mutex};
        pending_device = device;
        pending_swapchain = swapchain;
        pending_id = id;
    }
    changed.notify_all();
}

void Forget(vk::SwapchainKHR swapchain) {
    std::unique_lock lk{mutex};
    if (pending_swapchain == swapchain) {
        pending_id = 0;
    }
    changed.wait(lk, [&] { return waiting_on != swapchain; });
    last_scanout.store(0, std::memory_order_relaxed); // a new swapchain starts a new phase
}

std::int64_t LastScanoutNs() {
    return last_scanout.load(std::memory_order_relaxed);
}

} // namespace BbVblankSync

// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <cstdint>
#include "video_core/renderer_vulkan/vk_common.h"

/// ufc4 (BB_VBLANK_SYNC=1): when presented frames reached the screen (VK_KHR_present_wait), so
/// the port's virtual vblank can keep a fixed phase to the display's (bbport_vblank_sync.cpp).
namespace BbVblankSync {
/// After a successful present carrying `id` (VK_KHR_present_id) on `swapchain`.
void Presented(vk::Device device, vk::SwapchainKHR swapchain, std::uint64_t id);
/// Before `swapchain` is destroyed: stops waiting on it.
void Forget(vk::SwapchainKHR swapchain);
/// steady_clock time (ns) the latest waited-for frame reached the screen, 0 if none yet.
std::int64_t LastScanoutNs();
} // namespace BbVblankSync

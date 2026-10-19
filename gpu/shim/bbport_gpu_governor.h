// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

/// ufc4 (BB_GPU_GOVERNOR=1): frame-deadline GPU clock governor (bbport_gpu_governor.cpp).
namespace BbGpuGovernor {
/// Called once per guest flip: the time since the previous flip and the frame's deadline (ms).
void OnFlip(double interval_ms, double target_ms);
} // namespace BbGpuGovernor

// SPDX-License-Identifier: GPL-2.0-or-later
// ufc4 (BB_GPU_GOVERNOR=1): a frame-deadline GPU clock governor for AMD APUs on Linux.
//
// The driver's own governor follows GPU utilisation. This port feeds the GPU its frame late and
// in pieces, so the GPU is idle much of the time (utilisation 35-65 %) and stays at its lowest
// clock, yet the frame misses its vblank because its GPU work starts late. This governor looks at
// what matters: frames that missed their deadline. Every 500 ms it raises the GPU's minimum clock
// when frames were late while the GPU was busy, and lowers it after a few seconds without late
// frames, so the GPU runs as slow as the scene allows. It writes the amdgpu overdrive interface
// (pp_od_clk_voltage, power_dpm_force_performance_level), which Bazzite/SteamOS leave writable
// for the user; Steam may reset it, so it is re-applied every window. The launcher saves and
// restores the previous setting. Settings: BB_GPU_GOV_MIN/MAX/START (MHz, default 800/2000/1300).
#include "bbport_gpu_governor.h"
#ifdef __linux__

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <dirent.h>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>
#include <unistd.h>

namespace BbGpuGovernor {
namespace {

std::atomic<unsigned> frames{0}, late_frames{0};
std::once_flag started;
std::string device; // /sys/class/drm/cardN/device

int Env(const char* name, int fallback) {
    const char* v = std::getenv(name);
    return v && *v ? std::atoi(v) : fallback;
}

std::string ReadFile(const std::string& path) {
    std::ifstream in(path);
    std::string text((std::istreambuf_iterator<char>(in)), std::istreambuf_iterator<char>());
    return text;
}

bool WriteFile(const std::string& path, const std::string& text) {
    std::ofstream out(path);
    out << text;
    out.flush();
    return bool(out);
}

/// The first AMD GPU whose overdrive interface this user may write, else empty.
std::string FindDevice() {
    DIR* dir = opendir("/sys/class/drm");
    if (!dir) {
        return {};
    }
    std::string found;
    while (const dirent* e = readdir(dir)) {
        const std::string name = e->d_name;
        if (name.rfind("card", 0) != 0 || name.find('-') != std::string::npos) {
            continue;
        }
        const std::string dev = "/sys/class/drm/" + name + "/device";
        if (ReadFile(dev + "/vendor").rfind("0x1002", 0) == 0 &&
            access((dev + "/pp_od_clk_voltage").c_str(), W_OK) == 0 &&
            access((dev + "/power_dpm_force_performance_level").c_str(), W_OK) == 0) {
            found = dev;
            break;
        }
    }
    closedir(dir);
    return found;
}

/// The current overdrive minimum ("0: 1600Mhz" under OD_SCLK), or -1.
int CurrentMinimum() {
    const std::string od = ReadFile(device + "/pp_od_clk_voltage");
    const auto at = od.find("OD_SCLK:");
    if (at == std::string::npos) {
        return -1;
    }
    const auto zero = od.find("0:", at);
    return zero == std::string::npos ? -1 : std::atoi(od.c_str() + zero + 2);
}

bool Apply(int minimum, int maximum) {
    const bool manual = ReadFile(device + "/power_dpm_force_performance_level").rfind("manual", 0) == 0;
    if (manual && CurrentMinimum() == minimum) {
        return true; // nothing changed (Steam did not reset it either)
    }
    if (!manual && !WriteFile(device + "/power_dpm_force_performance_level", "manual")) {
        return false;
    }
    // One command per write: the interface parses a single line at a time.
    return WriteFile(device + "/pp_od_clk_voltage", "s 1 " + std::to_string(maximum)) &&
           WriteFile(device + "/pp_od_clk_voltage", "s 0 " + std::to_string(minimum)) &&
           WriteFile(device + "/pp_od_clk_voltage", "c");
}

void Run() {
    const int lowest = Env("BB_GPU_GOV_MIN", 800);
    const int highest = Env("BB_GPU_GOV_MAX", 2000);
    const int ceiling = Env("BB_GPU_GOV_CEILING", 2700); // the range's maximum, left to the driver
    int floor = std::clamp(Env("BB_GPU_GOV_START", 1300), lowest, highest);
    int calm = 0;
    std::printf("GPU governor: %s, minimum clock %d MHz (range %d-%d MHz)\n", device.c_str(), floor,
                lowest, highest);
    Apply(floor, ceiling);
    for (;;) {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        const unsigned n = frames.exchange(0), late = late_frames.exchange(0);
        const int busy = std::atoi(ReadFile(device + "/gpu_busy_percent").c_str());
        int next = floor;
        if (n >= 4 && late * 100 > n * 3 && busy >= 55) {
            // Late frames while the GPU works: more clock. (Late frames with an idle GPU are the
            // CPU's: a higher GPU clock would take power from it.)
            next = std::min(highest, floor + 200);
            calm = 0;
        } else if (late == 0 && n > 0) {
            if (++calm >= 6 && busy < 80) { // 3 s on time with headroom: try less clock
                next = std::max(lowest, floor - 100);
                calm = 0;
            }
        } else {
            calm = 0;
        }
        if (next != floor) {
            std::printf("GPU governor: minimum %d -> %d MHz (%u/%u frames late, GPU %d%% busy)\n", floor,
                        next, late, n, busy);
            std::fflush(stdout);
            floor = next;
        }
        Apply(floor, ceiling); // also re-applies after Steam reset the GPU to auto
    }
}

} // namespace

void OnFlip(double interval_ms, double target_ms) {
    static const bool enabled = [] {
        const char* v = std::getenv("BB_GPU_GOVERNOR");
        return v && *v == '1';
    }();
    if (!enabled) {
        return;
    }
    std::call_once(started, [] {
        device = FindDevice();
        if (device.empty()) {
            std::printf("GPU governor: no writable AMD GPU clock interface: off\n");
            return;
        }
        std::thread(Run).detach();
    });
    if (device.empty() || target_ms <= 0) {
        return;
    }
    frames.fetch_add(1, std::memory_order_relaxed);
    if (interval_ms > target_ms * 1.4) {
        late_frames.fetch_add(1, std::memory_order_relaxed);
    }
}

} // namespace BbGpuGovernor

#else
namespace BbGpuGovernor {
void OnFlip(double, double) {}
} // namespace BbGpuGovernor
#endif

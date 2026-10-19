// SPDX-License-Identifier: GPL-2.0-or-later
// ufc4 (BB_GPU_GOVERNOR=1): a frame-deadline GPU clock governor for AMD APUs on Linux.
//
// The driver's own governor follows GPU utilisation. This port feeds the GPU its frame late and
// in pieces, so the GPU is idle much of the time (utilisation 35-65 %) and stays at its lowest
// clock, yet the frame misses its vblank because its GPU work starts late. This governor looks at
// what matters: frames that missed their deadline. Every 500 ms it raises the GPU's minimum clock
// when frames were late while the GPU was busy (>= 75 %), lowers it when they were late with GPU
// headroom (< 60 %: the CPU is short of the shared power), and after a few seconds without late
// frames, so the GPU runs as slow as the scene allows. It writes the amdgpu overdrive interface
// (pp_od_clk_voltage, power_dpm_force_performance_level), which Bazzite/SteamOS leave writable
// for the user; Steam may reset it, so it is re-applied every window. The launcher saves and
// restores the previous setting. Settings: BB_GPU_GOV_MIN/MAX/START (MHz, default 800/2000/1300).
#include "bbport_gpu_governor.h"
#include "bbport_settings.h"
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

/// The current overdrive minimum (`level` 0, "0: 1600Mhz" under OD_SCLK) or maximum (1), or -1.
int CurrentClock(int level) {
    const std::string od = ReadFile(device + "/pp_od_clk_voltage");
    const auto at = od.find("OD_SCLK:");
    if (at == std::string::npos) {
        return -1;
    }
    const std::string tag = "\n" + std::to_string(level) + ":";
    const auto line = od.find(tag, at);
    return line == std::string::npos ? -1 : std::atoi(od.c_str() + line + tag.size());
}

bool Apply(int minimum, int maximum) {
    const bool manual = ReadFile(device + "/power_dpm_force_performance_level").rfind("manual", 0) == 0;
    if (manual && CurrentClock(0) == minimum && CurrentClock(1) == maximum) {
        return true; // nothing changed (Steam did not reset it either)
    }
    if (!manual && !WriteFile(device + "/power_dpm_force_performance_level", "manual")) {
        return false;
    }
    // One command per write: the interface parses a single line at a time. The range must stay
    // valid after each step: a maximum lowered below the current minimum goes in second.
    const std::string od = device + "/pp_od_clk_voltage";
    const std::string set_min = "s 0 " + std::to_string(minimum), set_max = "s 1 " + std::to_string(maximum);
    const bool lowering = maximum < CurrentClock(0);
    return WriteFile(od, lowering ? set_min : set_max) && WriteFile(od, lowering ? set_max : set_min) &&
           WriteFile(od, "c");
}

// The GPU's setting before the governor changed it, restored when the process exits (any
// launcher; launchers/legion-go/ufc4.sh also restores it, for a crash). Saved in Start().
std::string saved_level;
int saved_min = -1, saved_max = -1;
std::mutex apply_mutex;         // the thread's writes and the exit's restore never interleave
std::atomic<bool> stopped{false};

void Restore() {
    std::scoped_lock lk{apply_mutex};
    stopped = true; // the governor thread writes nothing after this
    if (device.empty() || saved_level.empty()) {
        return;
    }
    // Back to manual to set the range (written in a valid order), then the old level.
    WriteFile(device + "/power_dpm_force_performance_level", "manual");
    if (saved_min > 0 && saved_max > 0) {
        const std::string od = device + "/pp_od_clk_voltage";
        const bool lowering = saved_max < CurrentClock(0);
        const std::string set_min = "s 0 " + std::to_string(saved_min), set_max = "s 1 " + std::to_string(saved_max);
        WriteFile(od, lowering ? set_min : set_max);
        WriteFile(od, lowering ? set_max : set_min);
        WriteFile(od, "c");
    }
    WriteFile(device + "/power_dpm_force_performance_level", saved_level);
}

void Run() {
    const int lowest = Env("BB_GPU_GOV_MIN", 800);
    const int highest = Env("BB_GPU_GOV_MAX", 2000);
    const int ceiling = Env("BB_GPU_GOV_CEILING", 2700); // the range's maximum, left to the driver
    int floor = std::clamp(Env("BB_GPU_GOV_START", 1300), lowest, highest);
    int calm = 0;
    std::printf("GPU governor: %s, minimum clock %d MHz (range %d-%d MHz)\n", device.c_str(), floor,
                lowest, highest);
    {
        std::scoped_lock lk{apply_mutex};
        if (!stopped) {
            Apply(floor, ceiling);
        }
    }
    for (;;) {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        // The in-game menu's GPU power profile, live: the highest minimum and the range's maximum.
        const int profile = BbSettings::Get().gpu_profile;
        const bool profiled = profile >= 0 && profile < BbSettings::GpuProfileCount;
        const int top = profiled ? BbSettings::GpuProfiles[profile].floor_max : highest;
        const int max_clock = profiled ? BbSettings::GpuProfiles[profile].ceiling : ceiling;
        floor = std::min(floor, top);
        const unsigned n = frames.exchange(0), late = late_frames.exchange(0);
        const int busy = std::atoi(ReadFile(device + "/gpu_busy_percent").c_str());
        int next = floor;
        const bool lateness = n >= 4 && late * 100 > n * 3;
        if (lateness && busy >= 75) {
            // Late frames while the GPU is the bottleneck: more clock.
            next = std::min(top, floor + 200);
            calm = 0;
        } else if (lateness && busy < 60) {
            // Late frames with GPU headroom: the CPU is short (APUs share one power budget). A
            // higher GPU clock would take power from it: give some back. (Raising here was a trap:
            // at 18 W the GPU went to 2000 MHz at 53 % busy while the CPU fell to 0.9 GHz.)
            next = std::max(lowest, floor - 100);
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
        std::scoped_lock lk{apply_mutex};
        if (stopped) {
            return;
        }
        Apply(floor, max_clock); // also re-applies after Steam reset the GPU to auto
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
    // A frame deadline only exists when the vblank paces the frames: with an uncapped virtual
    // vblank (UFC 3's 480 Hz) the period says nothing about the frame time; no governor then.
    if (target_ms < 1000.0 / 120.0) {
        return;
    }
    std::call_once(started, [] {
        device = FindDevice();
        if (device.empty()) {
            std::printf("GPU governor: no writable AMD GPU clock interface: off\n");
            return;
        }
        // The setting from before the first start: a restart from the menu (the process
        // re-executes itself) inherits it instead of taking the governor's own as the original.
        if (const char* saved = std::getenv("BB_GPU_GOV_SAVED"); saved && *saved) {
            char level[32] = {};
            std::sscanf(saved, "%31[^,],%d,%d", level, &saved_min, &saved_max);
            saved_level = level;
        } else {
            std::string level = ReadFile(device + "/power_dpm_force_performance_level");
            while (!level.empty() && (level.back() == '\n' || level.back() == ' ')) {
                level.pop_back();
            }
            saved_level = level;
            saved_min = CurrentClock(0);
            saved_max = CurrentClock(1);
            const std::string value = saved_level + "," + std::to_string(saved_min) + "," + std::to_string(saved_max);
            setenv("BB_GPU_GOV_SAVED", value.c_str(), 1);
        }
        std::atexit(Restore);
        std::thread(Run).detach();
    });
    if (device.empty()) {
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

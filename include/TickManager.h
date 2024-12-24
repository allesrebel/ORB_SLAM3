#pragma once

#include <atomic>
#include <vector>
#include <chrono>

namespace ORB_SLAM3 
{

class TickManager 
{
private:
    std::atomic<int> elapsed_ticks;
    std::atomic<int> frame_count;
    std::vector<int> ticks_per_frame;
    std::atomic<int> frame_budget;

public:
    TickManager() = default;
    ~TickManager() = default;

    // Increment the frame's elapsed ticks
    void incrementTicks();

    // Signal the end of a frame and reset elapsed ticks, and actual time to do frame
    void endFrame(double&);

    // Calculate average ticks per frame
    double getAverageTicksPerFrame() const;

    // Debug print
    void printStats() const;
};

} // namespace ORB_SLAM3

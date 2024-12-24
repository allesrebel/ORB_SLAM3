#include "TickManager.h"

#include <iostream>
#include <numeric> 

namespace ORB_SLAM3 
{

void TickManager::incrementTicks()
{
    elapsed_ticks++;  // Increment the frame's elapsed ticks
}

// Signal the end of a frame and reset elapsed ticks
void TickManager::endFrame(double& actualFrameTime)
{
    frame_count++;
    ticks_per_frame.push_back(elapsed_ticks);

    // Using actual time elapsed to do frame as the budget for the next frame
    // frame_budget = 1/actualFrameTime * average_ticks_per_frame 
    frame_budget = static_cast<int>(1.0 / actualFrameTime * getAverageTicksPerFrame());

    // Reset for the next frame
    elapsed_ticks = 0;
}

// Calculate average ticks per frame
double TickManager::getAverageTicksPerFrame() const 
{
    if (ticks_per_frame.empty()) return 0.0;
    int total_ticks = std::accumulate(ticks_per_frame.begin(), ticks_per_frame.end(), 0);
    return static_cast<double>(total_ticks) / frame_count;
}

// Debug print
void TickManager::printStats() const
{
    std::cout << "Frame " << frame_count << " stats:\n";
    std::cout << " - Elapsed Ticks: " << elapsed_ticks << "\n";
    std::cout << " - Average Ticks Per Frame: " << getAverageTicksPerFrame() << "\n";
}

} // namespace ORB_SLAM3
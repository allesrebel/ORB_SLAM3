#include "TickManager.h"

#include <iostream>
#include <numeric> 

namespace ORB_SLAM3 
{

TickManager& TickManager::getInstance()
{
    static TickManager instance;
    return instance;
}

void TickManager::incrementTicks(const feature_extraction_settings_t& settings)
{
    elapsed_ticks++;  // Increment the frame's elapsed ticks
}

bool TickManager::skipCell(const feature_extraction_state_t& cell)
{
    return true;
}

// Signal the end of a frame and reset elapsed ticks
void TickManager::endFrame(double& actualFrameTime)
{
    // if no ticks were recorded, return
    if(elapsed_ticks == 0)
    {
        frame_budget = static_cast<int>(1.0 / actualFrameTime * getAverageTicksPerFrame());
        printStats(actualFrameTime);
        return;
    }

    ticks_per_frame.push_back(elapsed_ticks);

    // Using actual time elapsed to do frame as the budget for the next frame
    const double time_per_tick = ( actualFrameTime / getAverageTicksPerFrame());
    std::cout << "Time per tick: " << time_per_tick << std::endl;
    frame_budget = static_cast<int>( 50.0f / time_per_tick );

    // using the frame budget, we can figure out which mask to use!
    // we know how many levels of the pyramid we have, we also know
    // how many ticks per level, so we can figure out which fits the budget the best


    printStats(actualFrameTime);

    // Reset for the next frame
    elapsed_ticks = 0;
}

// Calculate average ticks per frame
double TickManager::getAverageTicksPerFrame() const 
{
    if (ticks_per_frame.empty()) return 0.0;
    int total_ticks = std::accumulate(ticks_per_frame.begin(), ticks_per_frame.end(), 0);
    return static_cast<double>(total_ticks) / ticks_per_frame.size();
}

// Debug print
void TickManager::printStats(double& frameTimestamp) const
{
    std::cout << "Frame finished in " << frameTimestamp << " ms stats:\n";
    std::cout << " - Recorded Frames: " << ticks_per_frame.size() << "\n";
    std::cout << " - Elapsed Ticks: " << elapsed_ticks << "\n";
    std::cout << " - Average Ticks Per Frame: " << getAverageTicksPerFrame() << "\n";
    std::cout << " - Frame Budget in Ticks: " << frame_budget << "\n";
}

} // namespace ORB_SLAM3
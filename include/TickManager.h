#pragma once

#include <atomic>
#include <vector>
#include <chrono>

namespace ORB_SLAM3 
{

struct feature_extraction_settings_t
{
    // These are the variables we need in order to figure out
    // how much time we have to provision to featurizing the frame
    int nlevels;  // pyramid levels
    int nCols;    // number of columns in the grid
    int nRows;    // number of rows in the grid

    // optional settings (TODO:)
    // bool enableFOV;
    // int maskHeight;
    // int maskWidth;
};

class TickManager 
{
private:
    std::atomic<int> elapsed_ticks;
    std::vector<int> ticks_per_frame;
    std::atomic<int> frame_budget;

    feature_extraction_settings_t settings;

public:

    // we'll use a singleton pattern so we can use this in multiple places 
    // (e.g. Frame, Tracking, etc.) while maintaining a single instance
    static TickManager& getInstance();

    // Increment the frame's elapsed ticks, and extraction settings
    void incrementTicks(feature_extraction_settings_t&);

    // Signal the end of a frame and reset elapsed ticks, and actual time to do frame
    void endFrame(double&);

    // Calculate average ticks per frame
    double getAverageTicksPerFrame() const;

    // Debug print
    void printStats(double&) const;

    // Delete copy constructor and assignment operator to enforce singleton pattern
    TickManager(const TickManager&) = delete;
    TickManager& operator=(const TickManager&) = delete;

private:
    // Only this class be making and destroying instances
    TickManager() = default;
    ~TickManager() = default;
};

} // namespace ORB_SLAM3

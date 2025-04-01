#pragma once

#include <atomic>
#include <vector>
#include <chrono>

namespace ORB_SLAM3 
{

// TODO, this is a placeholder for now
// Plan is to adjust SLAM settings later
struct feature_extraction_settings_t
{
    // int mnScaleLevels;
    // float mfScaleFactor;
    // float mfLogScaleFactor;
    // std::vector<float> mvScaleFactors;
    // std::vector<float> mvInvScaleFactors;
    // std::vector<float> mvLevelSigma2;
    // std::vector<float> mvInvLevelSigma2;
};

struct feature_extraction_state_t
{
    // These are the variables we need in order to figure out
    // how much time we have to provision to featurizing the frame
    int level;
    int col;
    int row;

    int nLevels;
    int nCols;
    int nRows;
};

class CellManager 
{
private:
    std::atomic<int> elapsed_cells;
    std::vector<int> cells_per_frame;
    std::atomic<int> frame_budget;
    std::atomic<bool> enableOasis = false;
    std::atomic<int> skip_frames = 0;
    mutable std::atomic<double> smoothedCellsPerFrame = 0.0; // EMA for smoothing
    double alpha = 0.5;                              // smoothing factor


    struct pyramid_level_t
    {
        int nRows;    // number of rows in the grid at this level
        int nCols;    // number of columns in the grid at this level
    };

    struct mask_t
    {
        int width;
        int height;
    };

    // an instance of the MASK struct we'll use!
    mask_t FOV_MASK;

    // These are the variables we need in order to figure out
    // how much time we have to provision to featurizing the frame
    std::vector<pyramid_level_t> pyramid_levels;

public:

    // we'll use a singleton pattern so we can use this in multiple places 
    // (e.g. Frame, Tracking, etc.) while maintaining a single instance
    static CellManager& getInstance();

    // Increment the frame's elapsed cells
    void incrementCell();

    // Skip Cell? 
    bool skipCell(const feature_extraction_state_t&);

    // Signal the end of a frame and reset elapsed cells, and actual time to do frame
    void endFrame(const double&, double);

    // Calculate average cells per frame
    double getAverageCellsPerFrame() const;

    // Debug print
    void printStats(const double&, const double&) const;

    // Delete copy constructor and assignment operator to enforce singleton pattern
    CellManager(const CellManager&) = delete;
    CellManager& operator=(const CellManager&) = delete;

private:
    // Only this class be making and destroying instances
    CellManager() = default;
    ~CellManager() = default;
};

} // namespace ORB_SLAM3

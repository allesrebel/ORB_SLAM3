#include "CellManager.h"

#include <iostream>
#include <fstream>
#include <numeric>

namespace ORB_SLAM3 
{

CellManager& CellManager::getInstance()
{
    static CellManager instance;
    return instance;
}

void CellManager::incrementCell()
{
    elapsed_cells++;  // Increment the frame's elapsed Cells
}

bool CellManager::skipCell(const feature_extraction_state_t& cell)
{
    bool skip = false;

    // check if we need to populate our pyramid with this level's info
    if( pyramid_levels.size() < (cell.level+1) )
    {
        pyramid_levels.push_back({cell.nRows, cell.nCols});
    }

    // check if we're skipping this cell, based on current FOV mask
    if( enableOasis )
    {
        const int maskWidth = FOV_MASK.width;
        const int maskHeight = FOV_MASK.height;
        // using the center of the cell to determine if it's in the FOV_MASK
        const int center_row = cell.nRows/2;
        const int center_col = cell.nCols/2;

        if( cell.row < center_row - maskHeight/2 || cell.row > center_row + maskHeight/2 )
        {
            skip = true;
        }

        if( cell.col < center_col - maskWidth/2 || cell.col > center_col + maskWidth/2 )
        {
            skip = true;
        }
    
        // check if we're skipping this cell, based on the number of frames we need to skip
        if( skip_frames )
        {
            skip = true;
        }
    }

    if( skip )
    {
        // We're skipping this cell, so we need to decrement the frame's elapsed Cells
        // to keep out this from the tracking stats
        elapsed_cells--;
    }

    return skip;
}

// Signal the end of a frame and reset elapsed Cells
void CellManager::endFrame(double& frame_num, double& actualFrameTime)
{

    // if we're skipping frames, decrement the number of frames we need to skip
    if( skip_frames )
    {
        std::cout << "Skipped/Dropped frame " << frame_num << std::endl;
        skip_frames--;
    }

    // if no Cells were recorded, return
    if(elapsed_cells == 0)
    {
        frame_budget = static_cast<int>(1.0 / actualFrameTime * getAverageCellsPerFrame());
        return;
    }

    if( skip_frames )
    {
        // we're skipping frames, so we don't need to calculate the budget
        // just reset the elapsed cells and return
        elapsed_cells = 0;
        return;
    }

    cells_per_frame.push_back(elapsed_cells);

    // Using actual time elapsed to do frame as the budget for the next frame
    const double time_per_cell = ( actualFrameTime / getAverageCellsPerFrame());

    // We know that the frame should take 50ms, so we can calculate the budget
    // based on when we're done with the frame, assumming actual time elapsed is < 50ms
    // if it's > 50ms, we'll have to adjust the budget accordingly
    const double frame_time = 50.0f; //ms
    double frame_budget = static_cast<int>( frame_time / time_per_cell );

    if( actualFrameTime > frame_time )   // if we're over budget, adjust the frame budget for the next frame
    {
        size_t frames_over_budget = 0;
        
        // see how many frames we're over budget
        while( actualFrameTime > frame_time )
        {
            frames_over_budget++;
            actualFrameTime -= frame_time;
        }

        // adjust number of frames over budget to account for 'dropped frames'
        skip_frames = static_cast<int>(frames_over_budget);

        // Assuming we're resuming at the same rate, we can calculate the remaining budget
        // We'll consume one of the skipped frames by accounting for the extra time needed
        // in this frame!
        const double remaining_budget = (2*frame_time) - actualFrameTime;
        if( skip_frames ) skip_frames--; // decrement!
        frame_budget =  static_cast<int>( remaining_budget / time_per_cell);
    }

    // Iterate through each mask size, calculating the number
    // of cells the proposed mask will cover, and compare that against
    // the frame budget, to determine if the mask should become FOV_MASK
    // starting with a 2x2 mask, and increasing in size, until budget is exceeded
    if(pyramid_levels.size() < 1)
    {
        // we don't have any pyramid levels, so we can't set the FOV_MASK
        std::cout << "No pyramid levels found, can't set FOV_MASK" << std::endl;
        return;
    }
    const int largest_mask = std::max(pyramid_levels[0].nRows, pyramid_levels[0].nCols) + 1;
    FOV_MASK.height = largest_mask + 1;
    FOV_MASK.width = largest_mask + 1;

    for( int mask = 2; mask < largest_mask; mask++ )
    {
        const int maskWidth = mask;
        const int maskHeight = mask;

        int cells_in_mask = 0;
        // Go through each pyramid level and calculate the number of cells
        // that would be covered by the mask
        for( int level = 0; level < pyramid_levels.size(); level++ )
        {
            const int cells_at_level = pyramid_levels[level].nRows * pyramid_levels[level].nCols;
            if( cells_at_level < (maskWidth * maskHeight) )
            {
                cells_in_mask += cells_at_level;
            }
            else
            {
                cells_in_mask += maskWidth * maskHeight;
            }
        }

        if( cells_in_mask < frame_budget )
        {
            // we're still in budget! keep going
            continue;
        }
        else
        {
            // We've found our mask size!
            // use the previous mask size to set the FOV_MASK
            const int prev_mask = mask - 1;
            FOV_MASK.height = prev_mask; 
            FOV_MASK.width = prev_mask;
            break;
        }
    }

    // We're warmed up and can start filtering cells!
    enableOasis = true;
    std::cout << "Frame " << frame_num << " finished in " << actualFrameTime << " ms stats:" << std::endl;
    std::cout << " - Recorded Frames: " << cells_per_frame.size() << std::endl;
    std::cout << " - Elapsed Cells: " << elapsed_cells << std::endl;
    std::cout << " - Average Cells Per Frame: " << getAverageCellsPerFrame() << std::endl;
    std::cout << " - Frame Budget in Cells: " << frame_budget << std::endl;
    std::cout << " - FOV Mask: " << FOV_MASK.width << "x" << FOV_MASK.height << std::endl;
    printStats(frame_num, actualFrameTime);

    // Reset for the next frame
    elapsed_cells = 0;
}

// Calculate average Cells per frame
double CellManager::getAverageCellsPerFrame() const 
{
    if (cells_per_frame.empty()) return 0.0;
    int total_cells = std::accumulate(cells_per_frame.begin(), cells_per_frame.end(), 0);
    return static_cast<double>(total_cells) / cells_per_frame.size();
}

// Debug print
void CellManager::printStats(double& frame_num, double& frameTimestamp) const
{
    // Open file in append mode
    std::ofstream file("cellManager.txt", std::ios::app);
    if (!file) {
        // Handle file open error
        std::cerr << "Failed to open cellManager.txt" << std::endl;
        return;
    }

    // Print out the pyramid levels (only once)
    static bool once = true;
    if (once)
    {
        file << " - Pyramid Level Cells: \n";
        for (size_t i = 0; i < pyramid_levels.size(); i++)
        {
            file << "   - Level " << i << ": " 
                 << pyramid_levels[i].nCols << "x" 
                 << pyramid_levels[i].nRows << "\n";
        }

        // Print out if oasis enabled
        file << (enableOasis ? " - Oasis Enabled" : " - Oasis Disabled") << std::endl;
        once = false;
    }

    file << "Frame " << frame_num << " finished in " << frameTimestamp << " ms stats:\n";
    file << " - Recorded Frames: " << cells_per_frame.size() << "\n";
    file << " - Elapsed Cells: " << elapsed_cells << "\n";
    file << " - Average Cells Per Frame: " << getAverageCellsPerFrame() << "\n";
    file << " - Frame Budget in Cells: " << frame_budget << "\n";
    
    // Print out the FOV_MASK
    file << " - FOV Mask: " << FOV_MASK.width << "x" << FOV_MASK.height << "\n";
}

} // namespace ORB_SLAM3

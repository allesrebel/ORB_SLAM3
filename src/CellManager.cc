#include "CellManager.h"

#include <iostream>
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
void CellManager::endFrame(long unsigned int& frame_num, double& actualFrameTime)
{
    // if no Cells were recorded, return
    if(elapsed_cells == 0)
    {
        frame_budget = static_cast<int>(1.0 / actualFrameTime * getAverageCellsPerFrame());
        return;
    }

    cells_per_frame.push_back(elapsed_cells);

    // Using actual time elapsed to do frame as the budget for the next frame
    const double time_per_cell = ( actualFrameTime / getAverageCellsPerFrame());
    frame_budget = static_cast<int>( 50.0f / time_per_cell );

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

    // printStats(frame_num, actualFrameTime);

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
void CellManager::printStats(long unsigned int& frame_num, double& frameTimestamp) const
{
    std::cout << "Frame " << frame_num << " finished in " << frameTimestamp << " ms stats:\n";
    std::cout << " - Recorded Frames: " << cells_per_frame.size() << "\n";
    std::cout << " - Elapsed Cells: " << elapsed_cells << "\n";
    std::cout << " - Average Cells Per Frame: " << getAverageCellsPerFrame() << "\n";
    std::cout << " - Frame Budget in Cells: " << frame_budget << "\n";

    // print out the FOV_MASK
    std::cout << " - FOV Mask: " << FOV_MASK.width << "x" << FOV_MASK.height << "\n";

    // print out the pyramid levels
    static bool once = true;
    if( once )
    {
        std::cout << " - Pyramid Level Cells: \n";
        for( int i = 0; i < pyramid_levels.size(); i++ )
        {
            std::cout << "   - Level " << i << ": " << pyramid_levels[i].nCols << "x" << pyramid_levels[i].nRows << "\n";
        }

        // print out if oasis enabled
        std::cout << ( enableOasis ? " - Oasis Enabled" : " - Oasis Disabled" ) << std::endl;

        once = false;
    }
}

} // namespace ORB_SLAM3
#pragma once

#include <cmath>
#include <limits>
#include <Eigen/Core>
#include <sophus/se3.hpp>

#include "Frame.h"
#include "Converter.h"          // Converter::toSE3f()

namespace ORB_SLAM3
{

/**
 *  Adaptive frame-skipping (omega SLAM) based on 
 *  Algorithm 1 (Billy et al.) 
 *  from https://www.scitepress.org/Link.aspx?doi=10.5220/0007386508400848
 *  
 * Keeps a frame when either
 *    - relative rotation change exceeds threshold
 *    - the sigma (skipped frames) counter fires
 */
class FrameSelector
{
public:
    // Defaults from Paper
    FrameSelector
    (
        float epsilon = 0.01,
        int sigma_max = 4,
        bool debug = false
    )
        : thres_(epsilon),
          sigma_(1),
          sigma_max_(sigma_max),
          debug(debug)
    { last_.id = std::numeric_limits<size_t>::max(); }

    // decide, *before* tracking, whether to process this frame
    bool accept(const Sophus::SE3f &Tcw_pred,
                size_t               id,
                double               stamp)
    {
        // always accept first frame
        if(last_.id == std::numeric_limits<size_t>::max())
        {
            updateLast(Tcw_pred,id,stamp);
            counter_++;
            return true;
        }

        Sophus::SE3f Trel = Tcw_pred * last_.Tcw.inverse();
        Eigen::Vector3f r_vec = Trel.so3().log();
        float ang_rad  = r_vec.norm();
        float ang_deg  = ang_rad * 180.f / M_PI;
        float trans       = Trel.translation().norm();

        // Note: vanilla omega slam only considers rotation 
        bool big_change = ( ang_rad > thres_ ); 

        bool keep_by_sigma = (sigma_ >= sigma_max_);

        if(debug)
        {
            std::cout << std::fixed << std::setprecision(3)
                      << "[Ω-SLAM]  ts=" << stamp
                      << "  id="    << id
                      << "  Δθ="    << ang_deg << "°"
                      << "  Δt="    << trans << " m"
                      << "  σ="     << sigma_
                      << "  keep="  << ( big_change || keep_by_sigma ?"Y":"N") << '\n';
        }

        if(big_change || keep_by_sigma)
        {
            // we're keeping
            updateLast(Tcw_pred,id,stamp);
            sigma_ = 1;
            counter_++;
            return true; 
        }
        else
        {
            // we're skipping
            sigma_++;
            return false;
        }
    }

private:
    struct MiniPose { Sophus::SE3f Tcw; size_t id; double t; } last_;

    inline void updateLast(const Sophus::SE3f &T,size_t i,double s)
    { last_.Tcw=T; last_.id=i; last_.t=s; }

    float  thres_;
    int    sigma_, sigma_max_;
    // number of kept frames
    size_t counter_ = 0;
    bool debug = false;
};
}; // Namespace

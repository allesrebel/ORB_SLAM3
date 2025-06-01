#pragma once
// MFSelector.hpp, header-only PID + feature-density selector for ORB-SLAM3
// --------------------------------------------------------------------------
// Depends only on the public ORB-SLAM3 headers (+ <chrono>/<memory>/<array>).
// Drop into include/  and add one line in Tracking.cc:
//
//   #include "MFSelector.hpp"
//
// Then, before each ExtractORB call do:
//
//   static ORB_SLAM3::MFSelector mfSel;
//   mpORBextractorLeft  = mfSel.extractorFor(lastPose, curPose);
//   mpORBextractorRight = mpORBextractorLeft;   // stereo/RGB-D can share
//
// Implementation is based on work by Pei, Yan et al. 
// A Methodology for Principled Approximation in Visual SLAM
// https://dl.acm.org/doi/10.1145/3410463.3414636
// Modified to work with ORBSLAM3's Pipeline
// NOTE: mf refers to number of features per frame

#include <array>
#include <chrono>
#include <memory>
#include <algorithm>
#include <vector>
#include <Eigen/Dense>

#include "ORBextractor.h"

namespace ORB_SLAM3 {

// Generic PID Controller, to implement the paper's version
class PID
{
public:
    PID(double kp, double ki, double kd,
        double minOut, double maxOut)
      : _kp(kp), _ki(ki), _kd(kd),
        _min(minOut), _max(maxOut),
        _integral(0.0), _prevErr(0.0),
        _first(true) {}

    // Update with the current error and return the control signal
    template<typename Clock = std::chrono::steady_clock>
    double update(double error)
    {
        const auto now = Clock::now();
        if (_first)
        {
            _last  = now;
            _first = false;
            _prevErr = error;
        }

        const double dt = std::chrono::duration<double>(now - _last).count();
        _last = now;

        // Integral term with anti-wind-up (clamp)
        _integral += error * dt;
        if (_ki != 0.0)
        {
            const double iCap = _max / _ki;
            _integral = std::clamp(_integral, -iCap, iCap);
        }

        const double deriv = (error - _prevErr) / (dt + 1e-9);
        _prevErr = error;

        double u = _kp * error + _ki * _integral + _kd * deriv;
        return std::clamp(u, _min, _max);
    }

private:
    const double _kp, _ki, _kd;
    const double _min, _max;
    double       _integral, _prevErr;
    bool         _first;
    std::chrono::steady_clock::time_point _last;
};

struct Extractors
{ 
    ORBextractor* left; 
    ORBextractor* right; 
};

// chooses among six ORBextractor variants to featurize a frame
class MFSelector
{
    // knob values from paper
    static constexpr std::array<int,6> MF_BUCKETS{{1000, 900, 800, 700, 600, 510}};
    static constexpr int               BUCKET_MAX = MF_BUCKETS.size() - 1;

public:
    // Build one extractor for every mf bucket up-front
    MFSelector(float scaleFactor = 1.2f,
               int   nlevels     = 8,
               int   iniThFAST   = 20,
               int   minThFAST   = 7,

               // PID gains (paper's defaults)
               double kp = 0.6, double ki = 0.04, double kd = 0.02,

               // Sliding-window weights for low/high bounds
               double alpha = 0.5,

               // Debug Logs
               bool debug = true
            )
    : _pid(kp, ki, kd, -BUCKET_MAX, BUCKET_MAX),
      _alpha(alpha),
      _idx(0),
      _debug(debug)
    {
        // TODO, replace with static initalizer?
        _left.reserve(MF_BUCKETS.size());
        _right.reserve(MF_BUCKETS.size());
        for (int mf : MF_BUCKETS)
        {
            _left.emplace_back(
                std::make_unique<ORBextractor>(
                    mf, scaleFactor, nlevels, iniThFAST, minThFAST,
                    false, 0, 0, false
                    // bool enableFOV, int maskHeight,int maskWidth, bool enableOasis
                ));
            _right.emplace_back(
                std::make_unique<ORBextractor>(
                    mf, scaleFactor, nlevels, iniThFAST, minThFAST,
                    false, 0, 0, false
                    // bool enableFOV, int maskHeight,int maskWidth, bool enableOasis
                ));
        }
    }

    // extractor chosen *for the NEXT frame*
    void updateExtractor
    (
        const Sophus::SE3<float>& Tprev_w2c,
        const Sophus::SE3<float>& Tcur_w2c
    )
    {
        // Pose distance (m)
        Sophus::SE3f Trel = Tcur_w2c * Tprev_w2c.inverse();
        const double d = Trel.translation().norm();

        // Do we have anything to compare against?
        if (_n == 0.0)
        {
            _dMin = _dMax = _dAvg = d;
            _n    = 1.0;
            return;
        }

        // Online statistics
        _dMin = std::min(_dMin, d);
        _dMax = std::max(_dMax, d);
        _dAvg = (_dAvg * _n + d) / (_n + 1.0);
        _n   += 1.0;

        // Dynamic low / high bounds
        const double D_low  = (1.0 - _alpha) * _dAvg + _alpha * _dMin;
        const double D_high = _alpha * _dAvg + (1.0 - _alpha) * _dMax;

        // PID error
        double err = 0.0;
        if (d < D_low)  err = -1.0;
        if (d > D_high) err = +1.0;

        const double inc = _pid.update(err);

        // Bucket index
        const int oldIdx = _idx;
        _idx = std::clamp(_idx + static_cast<int>(std::round(inc)),
                          0, BUCKET_MAX);

        if(_debug)
        {
            std::cout << std::fixed << std::setprecision(6)
                << "[MF-SEL] tPrev=("
                << "  d="      << d
                << "  dMin=" << _dMin
                << "  dAvg=" << _dAvg
                << "  dMax=" << _dMax
                << "  Dlo="  << D_low
                << "  Dhi="  << D_high
                << "  err="  << err
                << "  inc="  << inc
                << "  bucket " << oldIdx << "->" << _idx
                << "  (mf="   << MF_BUCKETS[_idx] << ")"
                << std::endl;
        }
    }

    // Current mf value in effect
    Extractors current() const
    { 
        return { _left [_idx].get(), _right[_idx].get() };
    }

private:
    // PID + stats
    PID    _pid;
    double _alpha;
    int    _idx;
    bool   _debug;

    double _dMin = std::numeric_limits<double>::infinity();
    double _dMax = 0.0;
    double _dAvg = 0.0;
    double _n    = 0.0;

    // Pool of ORBextractor instances
    std::vector<std::unique_ptr<ORBextractor>> _left, _right;
};

} // namespace

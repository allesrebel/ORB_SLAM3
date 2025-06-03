#pragma once
// SlimSLAM.hpp, an implementation of SLIM SLAM CORE for ORBSLAM3
// --------------------------------------------------------------------------
//
// This Implementation is based on work by Behroozi, Armand et al. 
// SlimSLAM: An Adaptive Runtime for Visual-Inertial Simultaneous Localization and Mapping
// https://dl.acm.org/doi/10.1145/3620666.3651361
#ifndef SLIMSLAM_HPP
#define SLIMSLAM_HPP

#include <string>
#include <vector>
#include <map>
#include <mutex> // For std::once_flag

namespace ORB_SLAM3
{

class SlimSLAM
{
public:
    // Static method to get the singleton instance
    // The instance is created on the first call and is thread-safe (C++11 onwards).
    static SlimSLAM& GetInstance();

    // Static method to initialize/configure the singleton instance.
    // This should be called once by the System class during its setup.
    // It retrieves the singleton instance and calls its internal configuration method.
    static void Initialize(const std::string& controlFilePath);

    // Delete copy constructor and assignment operator to prevent copies
    SlimSLAM(const SlimSLAM&) = delete;
    SlimSLAM& operator=(const SlimSLAM&) = delete;

    // Public interface methods
    void CheckAndApplyControls(double timestamp);
    
    // Used in ORBSLAM, how SlimSLAM Ultimately configures the SLAM
    int GetSkipFrames() { return mSkipFrames; }
    int GetKpMax() const { return mKpMax; }
    int GetKpMin() const { return mKpMin; }
    int GetProcessingMode() const { return mProcessingMode; }

    // Setter for direct override of processing mode (e.g., by System during training or specific scenarios)
    void SetSkipFrames(int input) { mSkipFrames = input; }
    void SetKpMax(int input) { mKpMax = input; }
    void SetKpMin(int input) { mKpMin = input; }
    void SetProcessingMode(int input) { mProcessingMode = input; }

private:
    // Private constructor ensures instantiation only via GetInstance's static local variable
    SlimSLAM();

    // Member function to load configuration, called by static Initialize via GetInstance()
    // This ensures that configuration logic is tied to the instance but triggered globally once.
    void ConfigureInstance(const std::string& filePath);
    void LoadControlFile(const std::string& filePath); // Actual file loading logic

    // Member variables for control parameters
    int mSkipFrames;
    int mKpMax;
    int mKpMin;
    int mProcessingMode;

    // Structure to hold a control command
    struct ControlCommand
    {
        std::string controlName;
        double value;
    };
    // Map to store control commands, keyed by timestamp
    std::map<double, std::vector<ControlCommand>> mControlCommands;

    // Ensures that the configuration (e.g., loading the control file)
    // happens only once for the singleton instance.
    std::once_flag m_configOnceFlag;
};

} // namespace ORB_SLAM3
#endif // SLIMSLAM_HPP
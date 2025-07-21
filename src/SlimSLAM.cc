// src/SlimSLAM.cc, an implementation of SLIM SLAM CORE for ORBSLAM3
// --------------------------------------------------------------------------
//
// This Implementation is based on work by Behroozi, Armand et al. 
// SlimSLAM: An Adaptive Runtime for Visual-Inertial Simultaneous Localization and Mapping
// https://dl.acm.org/doi/10.1145/3620666.3651361
#include "SlimSLAM.hpp"
#include <fstream>
#include <sstream>
#include <iostream>
#include <mutex> // Required for std::call_once

namespace ORB_SLAM3
{

// Private constructor: Initializes default control parameter values.
// Called implicitly by the static local variable in GetInstance() on its first use.
SlimSLAM::SlimSLAM() :
    mSkipFrames(0), mKpMax(200), mKpMin(180), mProcessingMode(2) // Default values
{
    // This message confirms the singleton instance is created.
    std::cout << "SLIMSLAM: Singleton instance created with default parameters." << std::endl;
}

// Static GetInstance method: Implements the Singleton pattern.
// Returns a reference to the single instance of SlimSLAM.
// The instance is created and initialized (constructor runs) on the first call.
// This is thread-safe for initialization from C++11 onwards.
SlimSLAM& SlimSLAM::GetInstance()
{
    static SlimSLAM instance; // The one and only instance
    return instance;
}

// Static Initialize method: Provides a global point to trigger the singleton's configuration.
// This should be called by the System class during its setup phase.
void SlimSLAM::Initialize(const std::string& controlFilePath)
{
    // Retrieve the singleton instance and call its member function to configure.
    GetInstance().ConfigureInstance(controlFilePath);
}

// Member function to configure the instance:
// Ensures that the core configuration logic (like loading a control file)
// runs exactly once for this singleton instance, using std::call_once.
void SlimSLAM::ConfigureInstance(const std::string& filePath)
{
    std::call_once(m_configOnceFlag, [&]() 
    {
        if (!filePath.empty()) 
        {
            this->LoadControlFile(filePath); // 'this->' is optional but can be explicit
        } else {
            std::cout << "SLIMSLAM: Instance configured without a control file (e.g., training mode or SlimSLAM disabled by System)." << std::endl;
        }
    });
    // If Initialize (and thus ConfigureInstance) is called multiple times,
    // the lambda passed to std::call_once will only execute its body on the very first call
    // associated with m_configOnceFlag for this instance.
}

// Loads control commands from the specified file.
// This is called by ConfigureInstance.
void SlimSLAM::LoadControlFile(const std::string& filePath)
{
    std::ifstream file(filePath);
    if (!file.is_open())
    {
        std::cerr << "SLIMSLAM: ERROR: Could not open control file: "
                  << filePath << std::endl;
        return;
    }

    mControlCommands.clear();
    std::string line;
    int commandCount = 0;

    while (std::getline(file, line))
    {
        if (line.empty() || line[0] == '#')
            continue;                          // skip blank / comment lines

        std::istringstream ss(line);
        std::string datasetStr, tsStr, ctrlStr, valStr;

        // CSV: dataset , timestamp , control_name , value
        if (!std::getline(ss, datasetStr, ','))      continue;
        if (!std::getline(ss, tsStr,     ','))      continue;
        if (!std::getline(ss, ctrlStr,   ','))      continue;
        if (!std::getline(ss, valStr))               continue; // rest of line

        try
        {
            double ts  = std::stod(tsStr);
            double val = std::stod(valStr);

            // Convert nanoseconds → seconds once on load
            if (ts > 1e12)
                ts /= 1e9;

            mControlCommands[ts].push_back({ctrlStr, val});
            ++commandCount;
        }
        catch (const std::exception& e)
        {
            std::cerr << "SLIMSLAM: WARNING: Malformed line in control file: \""
                      << line << "\" (" << e.what() << ')' << std::endl;
        }
    }

    if (commandCount)
    {
        std::cout << "SLIMSLAM: Control file loaded successfully with "
                  << commandCount << " commands across "
                  << mControlCommands.size() << " unique timestamps from: "
                  << filePath << std::endl;
    }
    else
    {
        std::cerr << "SLIMSLAM: WARNING: No valid commands parsed (file empty "
                     "or malformed): " << filePath << std::endl;
    }
}

// Checks for control commands at the given timestamp and applies them.
void SlimSLAM::CheckAndApplyControls(double timestamp)
{
    // Commands are applied only if the current frame's timestamp matches
    // a timestamp present in the control file.
    auto exact_match_it = mControlCommands.find(timestamp);
    if (exact_match_it != mControlCommands.end())
    {
        std::cout << "SLIMSLAM: Found commands for timestamp " << timestamp << std::endl;
        for (const auto& command : exact_match_it->second)
        {
            std::cout << "  Applying: " << command.controlName << " = " << command.value << std::endl;
            if (command.controlName == "Skip_Frames")
                mSkipFrames = static_cast<int>(command.value);
            else if (command.controlName == "KP_max")
                mKpMax = static_cast<int>(command.value);
            else if (command.controlName == "KP_min")
                mKpMin = static_cast<int>(command.value);
            else if (command.controlName == "Processing_Frames")
                mProcessingMode = static_cast<int>(command.value);
        }
    }
    else
    {
        // no match, apply default settings, Oracle didn't find an improvement
        mKpMax = 200;
        mKpMin = 180;
        mProcessingMode = 2;
        mSkipFrames = 0;
    }
}

} // namespace ORB_SLAM3


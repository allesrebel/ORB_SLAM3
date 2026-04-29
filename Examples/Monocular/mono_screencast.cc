/**
 * mono_screencast.cc — live desktop screen capture for ORB-SLAM3
 *
 * Feeds ORB-SLAM3 with continuous screenshots of the X11 desktop,
 * letting you watch the map build in real time as you move windows
 * or scroll content on screen.
 *
 * X11 headers are intentionally isolated in ScreenCapture.cpp to
 * prevent macro conflicts with Eigen/Sophus templates.
 *
 * Usage:
 *   ./mono_screencast path_to_vocabulary path_to_settings [:display]
 *
 * Example:
 *   cd Examples/Monocular
 *   ./mono_screencast ../../Vocabulary/ORBvoc.txt ScreenCapture.yaml :0
 *
 * Press Ctrl+C to stop and save the trajectory.
 */

#include <signal.h>
#include <iostream>
#include <chrono>
#include <thread>

#include <opencv2/core/core.hpp>
#include <opencv2/imgproc/imgproc.hpp>

#include <System.h>

#include "ScreenCapture.h"

using namespace std;

static bool g_running = true;

static void sigint_handler(int) {
    cout << "\nShutting down..." << endl;
    g_running = false;
}

int main(int argc, char** argv)
{
    if (argc < 3 || argc > 4) {
        cerr << "Usage: ./mono_screencast path_to_vocabulary path_to_settings [:display]\n"
             << "  :display defaults to the DISPLAY env var (usually :0)\n";
        return 1;
    }

    const char* display_name = (argc == 4) ? argv[3] : nullptr;

    ScreenCapture cap(display_name);
    if (!cap.valid())
        return 1;

    cout << "Screen resolution: " << cap.width() << "x" << cap.height() << "\n";

    struct sigaction sa{};
    sa.sa_handler = sigint_handler;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT, &sa, nullptr);

    ORB_SLAM3::System SLAM(argv[1], argv[2], ORB_SLAM3::System::MONOCULAR, /*viewer=*/true);
    const float imageScale = SLAM.GetImageScale();

    cout << "Screen capture SLAM running. Press Ctrl+C to stop.\n";

    using Clock   = std::chrono::steady_clock;
    using Seconds = std::chrono::duration<double>;

    const double target_fps = 30.0;
    const double frame_dt   = 1.0 / target_fps;

    while (g_running && !SLAM.isShutDown()) {
        auto t0 = Clock::now();

        double timestamp = std::chrono::duration_cast<Seconds>(
            std::chrono::system_clock::now().time_since_epoch()).count();

        cv::Mat frame = cap.capture();
        if (frame.empty()) {
            cerr << "XGetImage failed, skipping frame\n";
            this_thread::sleep_for(chrono::milliseconds(33));
            continue;
        }

        if (imageScale != 1.f) {
            int w = static_cast<int>(frame.cols * imageScale);
            int h = static_cast<int>(frame.rows * imageScale);
            cv::resize(frame, frame, cv::Size(w, h));
        }

        SLAM.TrackMonocular(frame, timestamp);

        double elapsed = chrono::duration_cast<Seconds>(Clock::now() - t0).count();
        if (elapsed < frame_dt)
            this_thread::sleep_for(chrono::duration<double>(frame_dt - elapsed));
    }

    SLAM.Shutdown();
    SLAM.SaveKeyFrameTrajectoryTUM("KeyFrameTrajectory.txt");
    cout << "Trajectory saved to KeyFrameTrajectory.txt\n";
    return 0;
}

// mono_screencast_stream.cc — drive ORB-SLAM3 from anything cv::VideoCapture
// can open: a local file, an RTSP/HTTP URL, a UDP MPEG-TS stream, etc.
//
// Useful for two scenarios that the existing image-directory driver can't cover:
//   - decoding a video file in-process (no on-disk frame extraction step)
//   - reading a live network stream (UDP/RTSP) in real time
//
// Usage:
//   mono_screencast_stream <vocab> <settings> <source> [max_seconds]
// where <source> is anything OpenCV's VideoCapture accepts.

#include <atomic>
#include <chrono>
#include <csignal>
#include <iostream>
#include <string>

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/videoio.hpp>

#include <System.h>

namespace {
std::atomic<bool> g_running{true};
void on_sigint(int) { g_running = false; }
}

int main(int argc, char** argv)
{
    if (argc < 4 || argc > 5) {
        std::cerr << "Usage: " << argv[0]
                  << " <vocab> <settings> <source> [max_seconds]\n"
                  << "  <source> is any URL/path cv::VideoCapture can open\n";
        return 1;
    }
    const std::string vocab    = argv[1];
    const std::string settings = argv[2];
    const std::string source   = argv[3];
    const double max_seconds   = (argc == 5) ? std::stod(argv[4]) : 0.0;

    struct sigaction sa{};
    sa.sa_handler = on_sigint;
    sigemptyset(&sa.sa_mask);
    sigaction(SIGINT,  &sa, nullptr);
    sigaction(SIGTERM, &sa, nullptr);

    cv::VideoCapture cap;
    bool opened = false;
    // If the source is digits, treat it as a camera index; otherwise pass
    // the string through (covers files and URLs). Force the FFmpeg backend
    // for files/URLs because OpenCV's GStreamer backend frequently lacks
    // UDP/RTSP plugins on stock Ubuntu builds.
    bool all_digits = !source.empty() &&
        std::all_of(source.begin(), source.end(),
                    [](char c){ return std::isdigit(static_cast<unsigned char>(c)); });
    if (all_digits) {
        opened = cap.open(std::stoi(source));
    } else {
        opened = cap.open(source, cv::CAP_FFMPEG);
        if (!opened) {
            std::cerr << "FFmpeg backend failed, retrying with CAP_ANY...\n";
            opened = cap.open(source, cv::CAP_ANY);
        }
    }
    if (!opened) {
        std::cerr << "Failed to open VideoCapture source: " << source << "\n";
        return 1;
    }

    const double cap_fps = cap.get(cv::CAP_PROP_FPS);
    const int    cap_w   = static_cast<int>(cap.get(cv::CAP_PROP_FRAME_WIDTH));
    const int    cap_h   = static_cast<int>(cap.get(cv::CAP_PROP_FRAME_HEIGHT));
    std::cout << "VideoCapture opened: " << source
              << " (" << cap_w << "x" << cap_h
              << " @ " << cap_fps << " fps reported)\n";

    ORB_SLAM3::System SLAM(vocab, settings, ORB_SLAM3::System::MONOCULAR,
                           /*viewer=*/false);
    const float imageScale = SLAM.GetImageScale();

    using Clock   = std::chrono::steady_clock;
    using Seconds = std::chrono::duration<double>;
    const auto t_start = Clock::now();

    int fed = 0, dropped = 0;
    cv::Mat im;

    while (g_running && !SLAM.isShutDown()) {
        if (!cap.read(im) || im.empty()) {
            // End-of-file for a regular file; for a stream this could be a
            // transient hiccup. We treat both as terminal so the test exits
            // promptly — change here if a re-connect loop is desired.
            std::cout << "Stream ended after " << fed << " frames\n";
            break;
        }

        if (im.channels() == 4)
            cv::cvtColor(im, im, cv::COLOR_BGRA2BGR);

        if (imageScale != 1.f) {
            int w = static_cast<int>(im.cols * imageScale);
            int h = static_cast<int>(im.rows * imageScale);
            cv::resize(im, im, cv::Size(w, h));
        }

        // Synthesised wall-clock timestamp — for SLAM all that matters is
        // monotonic, well-spaced timestamps in seconds.
        double t = std::chrono::duration_cast<Seconds>(
                       Clock::now() - t_start).count();

        auto t0 = Clock::now();
        SLAM.TrackMonocular(im, t);
        auto t1 = Clock::now();
        double track_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();

        ++fed;
        if (fed % 30 == 0 || fed <= 5) {
            std::cout << "[" << fed << "] " << im.cols << "x" << im.rows
                      << "  t=" << t << "s  track=" << track_ms << " ms\n";
        }

        if (max_seconds > 0.0 && t >= max_seconds) {
            std::cout << "Reached max_seconds=" << max_seconds
                      << ", stopping after " << fed << " frames\n";
            break;
        }
    }

    cap.release();
    SLAM.Shutdown();
    SLAM.SaveKeyFrameTrajectoryTUM("KeyFrameTrajectory.txt");
    SLAM.SaveMapPLY("Map.ply");

    std::cout << "\n--- Summary ---\n"
              << "Frames fed:    " << fed     << "\n"
              << "Frames dropped:" << dropped << "\n"
              << "Trajectory:    KeyFrameTrajectory.txt\n"
              << "Map dump:      Map.ply\n";
    return 0;
}

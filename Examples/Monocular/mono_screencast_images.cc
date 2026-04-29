/**
 * mono_screencast_images.cc — offline image-sequence driver for ORB-SLAM3
 *
 * Replays a directory of desktop screenshots as if they were live screen
 * captures. Useful for validating the screencast pipeline without needing
 * a real X server — same SLAM path as mono_screencast, but the frames
 * come from disk instead of XGetImage.
 *
 * Usage:
 *   ./mono_screencast_images <vocab> <settings> <image_dir> [fps]
 *
 * The image directory is read in sorted filename order. PNG, JPG, JPEG,
 * and BMP files are accepted. Timestamps are synthesized at 1/fps spacing.
 */

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <iostream>
#include <thread>
#include <vector>

#include <opencv2/core/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc/imgproc.hpp>

#include <System.h>

namespace fs = std::filesystem;

static bool is_image_file(const fs::path& p)
{
    static const std::vector<std::string> exts = {
        ".png", ".PNG", ".jpg", ".JPG", ".jpeg", ".JPEG", ".bmp", ".BMP"
    };
    auto ext = p.extension().string();
    return std::find(exts.begin(), exts.end(), ext) != exts.end();
}

int main(int argc, char** argv)
{
    if (argc < 4 || argc > 5) {
        std::cerr << "Usage: ./mono_screencast_images <vocab> <settings> <image_dir> [fps]\n";
        return 1;
    }

    const std::string vocab    = argv[1];
    const std::string settings = argv[2];
    const std::string img_dir  = argv[3];
    const double fps           = (argc == 5) ? std::stod(argv[4]) : 30.0;

    if (!fs::is_directory(img_dir)) {
        std::cerr << "Not a directory: " << img_dir << "\n";
        return 1;
    }

    std::vector<fs::path> files;
    for (const auto& entry : fs::directory_iterator(img_dir)) {
        if (entry.is_regular_file() && is_image_file(entry.path()))
            files.push_back(entry.path());
    }
    std::sort(files.begin(), files.end());

    if (files.empty()) {
        std::cerr << "No images found in " << img_dir << "\n";
        return 1;
    }

    std::cout << "Loaded " << files.size() << " images from " << img_dir << "\n";
    std::cout << "Synthetic timestamps at " << fps << " fps\n";

    ORB_SLAM3::System SLAM(vocab, settings, ORB_SLAM3::System::MONOCULAR, /*viewer=*/false);
    const float imageScale = SLAM.GetImageScale();

    const double dt = 1.0 / fps;
    int fed = 0, skipped = 0;

    for (size_t i = 0; i < files.size(); ++i) {
        cv::Mat im = cv::imread(files[i].string(), cv::IMREAD_UNCHANGED);
        if (im.empty()) {
            std::cerr << "Failed to load " << files[i] << " — skipping\n";
            ++skipped;
            continue;
        }

        if (im.channels() == 4)
            cv::cvtColor(im, im, cv::COLOR_BGRA2BGR);

        if (imageScale != 1.f) {
            int w = static_cast<int>(im.cols * imageScale);
            int h = static_cast<int>(im.rows * imageScale);
            cv::resize(im, im, cv::Size(w, h));
        }

        const double timestamp = i * dt;
        auto t0 = std::chrono::steady_clock::now();
        SLAM.TrackMonocular(im, timestamp);
        auto t1 = std::chrono::steady_clock::now();

        double track_ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
        std::cout << "[" << (i + 1) << "/" << files.size() << "] "
                  << files[i].filename().string()
                  << "  " << im.cols << "x" << im.rows
                  << "  track=" << track_ms << " ms\n";
        ++fed;
    }

    SLAM.Shutdown();
    SLAM.SaveKeyFrameTrajectoryTUM("KeyFrameTrajectory.txt");
    SLAM.SaveMapPLY("Map.ply");

    std::cout << "\n--- Summary ---\n";
    std::cout << "Frames fed:    " << fed << "\n";
    std::cout << "Frames failed: " << skipped << "\n";
    std::cout << "Trajectory:    KeyFrameTrajectory.txt\n";
    std::cout << "Map dump:      Map.ply\n";
    return 0;
}

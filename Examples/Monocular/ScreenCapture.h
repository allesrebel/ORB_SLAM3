#pragma once
#include <opencv2/core/core.hpp>

// Thin wrapper around X11 screen capture.
// X11 headers are confined to ScreenCapture.cpp so they never collide
// with Eigen / Sophus template definitions in the main translation unit.
class ScreenCapture {
public:
    explicit ScreenCapture(const char* display_name = nullptr);
    ~ScreenCapture();

    // Returns a grayscale cv::Mat, or empty Mat on failure.
    cv::Mat capture();

    int  width()  const { return w_; }
    int  height() const { return h_; }
    bool valid()  const { return dpy_ != nullptr; }

private:
    void*          dpy_;   // Display*  — opaque to callers
    unsigned long  root_;  // Window    — opaque to callers
    int            w_, h_;
};

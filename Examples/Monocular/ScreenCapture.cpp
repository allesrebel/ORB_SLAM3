// X11 headers are ONLY included here — never in mono_screencast.cc —
// to prevent macro pollution of Eigen/Sophus template definitions.

#include "ScreenCapture.h"

#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <opencv2/imgproc/imgproc.hpp>
#include <iostream>

ScreenCapture::ScreenCapture(const char* display_name)
    : dpy_(nullptr), root_(0), w_(0), h_(0)
{
    Display* dpy = XOpenDisplay(display_name);
    if (!dpy) {
        const char* env = getenv("DISPLAY");
        std::cerr << "Failed to open X11 display '"
                  << (display_name ? display_name : (env ? env : "(unset)"))
                  << "'.\nMake sure $DISPLAY is set and you are in a graphical session.\n";
        return;
    }

    Window root = DefaultRootWindow(dpy);
    XWindowAttributes attrs;
    XGetWindowAttributes(dpy, root, &attrs);

    dpy_  = dpy;
    root_ = static_cast<unsigned long>(root);
    w_    = attrs.width;
    h_    = attrs.height;
}

ScreenCapture::~ScreenCapture()
{
    if (dpy_)
        XCloseDisplay(static_cast<Display*>(dpy_));
}

cv::Mat ScreenCapture::capture()
{
    if (!dpy_)
        return cv::Mat();

    Display* dpy  = static_cast<Display*>(dpy_);
    Window   root = static_cast<Window>(root_);

    XImage* img = XGetImage(dpy, root, 0, 0, w_, h_, AllPlanes, ZPixmap);
    if (!img)
        return cv::Mat();

    // XImage data is 32-bit BGRX on most X11 servers. Use the actual
    // bytes_per_line from the XImage as the cv::Mat row stride — XServers
    // routinely pad rows for alignment, and assuming stride == w*4 silently
    // gives sheared/garbled images that look superficially OK but break ORB
    // feature matching. Drop the unused alpha channel and return BGR so the
    // frame matches the rest of the screencast pipeline (Camera.RGB: 0).
    // SLAM does its own grayscale conversion downstream.
    cv::Mat bgra(h_, w_, CV_8UC4, img->data,
                 static_cast<size_t>(img->bytes_per_line));
    cv::Mat bgr;
    cv::cvtColor(bgra, bgr, cv::COLOR_BGRA2BGR);

    // X11 returns pixel-perfect screen content. UI elements (window borders,
    // text, sharp rectangles) end up with hard aliased edges that shift by
    // sub-pixel amounts between captures whenever the display compositor
    // re-rasterises a frame. Those sub-pixel shifts make ORB descriptors
    // around those edges fail to match between consecutive frames, blocking
    // monocular initialisation. A 1-pixel Gaussian blur emulates the natural
    // anti-aliasing of an LCD and is what makes feature tracking stable.
    cv::Mat smoothed;
    cv::GaussianBlur(bgr, smoothed, cv::Size(0, 0), /*sigma=*/1.0);
    XDestroyImage(img);
    return smoothed;
}

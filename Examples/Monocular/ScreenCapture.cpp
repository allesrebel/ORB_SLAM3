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

    // XImage data is 32-bit BGRX on most X11 servers.
    cv::Mat bgra(h_, w_, CV_8UC4, img->data);
    cv::Mat gray;
    cv::cvtColor(bgra, gray, cv::COLOR_BGRA2GRAY);
    cv::Mat result = gray.clone();   // clone before freeing XImage backing buffer
    XDestroyImage(img);
    return result;
}

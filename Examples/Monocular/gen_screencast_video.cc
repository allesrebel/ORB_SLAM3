// gen_screencast_video.cc — synthesise a screencast-style test video.
//
// Renders a textured "desktop" with several UI window panels at different
// 3D depths, a moving mouse cursor, window navigation (focus changes) and
// window movement (panels slide). A virtual pinhole camera dollies and pans
// over the scene so each frame has true depth-dependent parallax — enough
// for ORB-SLAM3 monocular initialisation.
//
// Usage:
//   gen_screencast_video <out.mp4> [width] [height] [fps] [seconds]
// Defaults: 1280 720 30 12

#include <cmath>
#include <iostream>
#include <random>
#include <string>
#include <vector>

#include <opencv2/core.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/videoio.hpp>

namespace {

cv::Mat make_window_panel(int w, int h, const std::string& title,
                          const cv::Scalar& titlebar, const cv::Scalar& body,
                          int seed)
{
    cv::Mat img(h, w, CV_8UC3, body);

    const int bar_h = std::max(28, h / 14);
    cv::rectangle(img, cv::Rect(0, 0, w, bar_h), titlebar, cv::FILLED);

    for (int i = 0; i < 3; ++i) {
        cv::Scalar btn = (i == 0) ? cv::Scalar(60, 60, 220)
                       : (i == 1) ? cv::Scalar(60, 200, 220)
                                  : cv::Scalar(70, 200, 90);
        cv::circle(img, cv::Point(14 + i * 22, bar_h / 2),
                   bar_h / 4, btn, cv::FILLED);
    }
    cv::putText(img, title, cv::Point(90, bar_h - 8),
                cv::FONT_HERSHEY_SIMPLEX, 0.7,
                cv::Scalar(245, 245, 245), 2, cv::LINE_AA);

    std::mt19937 rng(seed);
    std::uniform_int_distribution<int> col(40, 230);

    // Fake content rows — text-like blocks of varying widths.
    int y = bar_h + 14;
    while (y < h - 16) {
        int x = 16;
        int row_h = 14 + (rng() % 8);
        while (x < w - 24) {
            int bw = 30 + (rng() % 120);
            if (x + bw > w - 24) break;
            cv::Scalar c(col(rng), col(rng), col(rng));
            cv::rectangle(img,
                          cv::Rect(x, y, bw, row_h),
                          c, cv::FILLED);
            x += bw + 8 + (rng() % 12);
        }
        y += row_h + 10;
    }

    // A few "icons" — high-contrast shapes that ORB will love.
    for (int k = 0; k < 8; ++k) {
        int cx = 30 + (rng() % (w - 60));
        int cy = bar_h + 10 + (rng() % (h - bar_h - 30));
        int r  = 8 + (rng() % 14);
        cv::Scalar c(col(rng), col(rng), col(rng));
        if (k % 2 == 0)
            cv::circle(img, cv::Point(cx, cy), r, c, cv::FILLED);
        else
            cv::rectangle(img, cv::Rect(cx - r, cy - r, 2 * r, 2 * r),
                          c, cv::FILLED);
    }

    cv::rectangle(img, cv::Rect(0, 0, w, h),
                  cv::Scalar(20, 20, 20), 2);
    return img;
}

cv::Mat make_background(int w, int h)
{
    cv::Mat bg(h, w, CV_8UC3);
    for (int y = 0; y < h; ++y) {
        for (int x = 0; x < w; ++x) {
            int r = static_cast<int>(40 + 60.0 * x / w);
            int g = static_cast<int>(60 + 80.0 * y / h);
            int b = static_cast<int>(90 + 60.0 * (x + y) / (w + h));
            bg.at<cv::Vec3b>(y, x) =
                cv::Vec3b(static_cast<uchar>(b),
                          static_cast<uchar>(g),
                          static_cast<uchar>(r));
        }
    }
    // Sprinkle "wallpaper" dots so the background is feature-rich
    // even where no window covers it.
    std::mt19937 rng(31337);
    for (int i = 0; i < 800; ++i) {
        int x = rng() % w, y = rng() % h, r = 2 + (rng() % 5);
        cv::Scalar c(40 + (rng() % 120), 40 + (rng() % 120), 40 + (rng() % 120));
        cv::circle(bg, cv::Point(x, y), r, c, cv::FILLED);
    }
    return bg;
}

void draw_cursor(cv::Mat& img, cv::Point2f p, bool clicking)
{
    std::vector<cv::Point> pts = {
        cv::Point(static_cast<int>(p.x),       static_cast<int>(p.y)),
        cv::Point(static_cast<int>(p.x + 16),  static_cast<int>(p.y + 6)),
        cv::Point(static_cast<int>(p.x + 7),   static_cast<int>(p.y + 8)),
        cv::Point(static_cast<int>(p.x + 12),  static_cast<int>(p.y + 18)),
        cv::Point(static_cast<int>(p.x + 9),   static_cast<int>(p.y + 19)),
        cv::Point(static_cast<int>(p.x + 4),   static_cast<int>(p.y + 11)),
        cv::Point(static_cast<int>(p.x + 0),   static_cast<int>(p.y + 16)),
    };
    cv::Scalar fill = clicking ? cv::Scalar(0, 220, 255)
                               : cv::Scalar(255, 255, 255);
    cv::fillPoly(img, std::vector<std::vector<cv::Point>>{pts}, fill);
    cv::polylines(img, std::vector<std::vector<cv::Point>>{pts},
                  /*closed=*/true, cv::Scalar(0, 0, 0), 2, cv::LINE_AA);
}

struct Panel {
    cv::Mat       texture;     // pre-rendered window content
    cv::Vec3f     center;      // world position of the panel center
    cv::Size2f    size;        // world size
    int           focus_start; // frame at which it becomes "focused"
    int           focus_len;   // frames focused
};

// Project a 3D point through a pinhole camera with the given pose.
cv::Point2f project(const cv::Vec3f& Xw,
                    const cv::Matx33f& K,
                    const cv::Matx33f& R,
                    const cv::Vec3f& t)
{
    cv::Vec3f Xc = R * Xw + t;
    if (Xc[2] < 1e-3f) Xc[2] = 1e-3f;
    cv::Vec3f x = K * Xc;
    return cv::Point2f(x[0] / x[2], x[1] / x[2]);
}

cv::Matx33f rot_y(float a)
{
    float c = std::cos(a), s = std::sin(a);
    return cv::Matx33f(c, 0, s,  0, 1, 0,  -s, 0, c);
}
cv::Matx33f rot_x(float a)
{
    float c = std::cos(a), s = std::sin(a);
    return cv::Matx33f(1, 0, 0,  0, c, -s,  0, s, c);
}

} // namespace

int main(int argc, char** argv)
{
    if (argc < 2) {
        std::cerr << "Usage: " << argv[0]
                  << " <out.mp4> [width] [height] [fps] [seconds]\n";
        return 1;
    }
    const std::string out_path = argv[1];
    const int   W       = (argc > 2) ? std::stoi(argv[2]) : 1280;
    const int   H       = (argc > 3) ? std::stoi(argv[3]) : 720;
    const int   FPS     = (argc > 4) ? std::stoi(argv[4]) : 30;
    const float SECS    = (argc > 5) ? std::stof(argv[5]) : 12.0f;
    const int   N       = static_cast<int>(SECS * FPS);

    // Camera intrinsics — matches the YAML config exactly.
    const float fx = 800.0f, fy = 800.0f;
    const float cx = W * 0.5f, cy = H * 0.5f;
    const cv::Matx33f K(fx, 0, cx,
                        0, fy, cy,
                        0,  0,  1);

    // Build the desktop scene: panels at varying 3D depths.
    std::vector<Panel> panels;
    panels.push_back({make_window_panel(640, 420, "Terminal — bash",
                                        cv::Scalar(60, 60, 60),
                                        cv::Scalar(20, 20, 25), 1),
                      cv::Vec3f(-1.6f,  0.4f, 6.0f),
                      cv::Size2f(2.6f, 1.7f),
                      30, 90});
    panels.push_back({make_window_panel(720, 480, "Firefox — orbslam3.org",
                                        cv::Scalar(180, 80, 30),
                                        cv::Scalar(245, 245, 250), 2),
                      cv::Vec3f( 1.4f, -0.2f, 5.2f),
                      cv::Size2f(3.0f, 2.0f),
                      130, 90});
    panels.push_back({make_window_panel(560, 380, "Files — ~/Projects",
                                        cv::Scalar(100, 100, 180),
                                        cv::Scalar(245, 240, 230), 3),
                      cv::Vec3f(-0.4f, -1.4f, 7.5f),
                      cv::Size2f(2.4f, 1.6f),
                      230, 90});
    panels.push_back({make_window_panel(520, 360, "Settings — Display",
                                        cv::Scalar(120, 80, 120),
                                        cv::Scalar(240, 230, 245), 4),
                      cv::Vec3f( 0.6f,  1.2f, 8.5f),
                      cv::Size2f(2.2f, 1.5f),
                      330, 90});

    cv::Mat bg = make_background(W, H);

    // VideoWriter — pick a codec the system actually supports.
    int fourccs[] = {
        cv::VideoWriter::fourcc('m','p','4','v'),
        cv::VideoWriter::fourcc('a','v','c','1'),
        cv::VideoWriter::fourcc('M','J','P','G'),
    };
    cv::VideoWriter writer;
    for (int fcc : fourccs) {
        writer.open(out_path, fcc, FPS, cv::Size(W, H), true);
        if (writer.isOpened()) {
            std::cout << "Encoding with FOURCC=0x" << std::hex << fcc << std::dec << "\n";
            break;
        }
    }
    if (!writer.isOpened()) {
        std::cerr << "Failed to open VideoWriter for " << out_path << "\n";
        return 1;
    }

    std::cout << "Rendering " << N << " frames @ " << FPS << " fps -> " << out_path << "\n";

    for (int f = 0; f < N; ++f) {
        const float t = static_cast<float>(f) / FPS;

        // Camera path: gentle dolly + small yaw + small pitch.
        // Translation is meaningful so monocular SLAM can triangulate.
        cv::Vec3f cam_t(0.6f * std::sin(0.35f * t),
                        0.25f * std::sin(0.22f * t + 0.3f),
                        -0.6f * std::sin(0.18f * t));
        cv::Matx33f R_w2c = rot_x(0.06f * std::sin(0.20f * t)) *
                            rot_y(0.18f * std::sin(0.30f * t));

        // World-to-camera: Xc = R * (Xw - cam_t)
        cv::Vec3f t_w2c = -(R_w2c * cam_t);

        cv::Mat frame = bg.clone();

        // Render panels back-to-front (painter's algorithm by depth in cam frame).
        std::vector<int> order(panels.size());
        for (size_t i = 0; i < panels.size(); ++i) order[i] = static_cast<int>(i);
        std::sort(order.begin(), order.end(), [&](int a, int b) {
            float za = (R_w2c * panels[a].center + t_w2c)[2];
            float zb = (R_w2c * panels[b].center + t_w2c)[2];
            return za > zb; // far first
        });

        for (int idx : order) {
            Panel& p = panels[idx];

            // Window movement: each window slowly slides in its plane.
            cv::Vec3f drift(0.25f * std::sin(0.4f * t + idx),
                            0.15f * std::cos(0.3f * t + idx),
                            0.0f);
            cv::Vec3f c = p.center + drift;

            float hw = p.size.width  * 0.5f;
            float hh = p.size.height * 0.5f;
            cv::Vec3f corners_w[4] = {
                c + cv::Vec3f(-hw, -hh, 0),
                c + cv::Vec3f( hw, -hh, 0),
                c + cv::Vec3f( hw,  hh, 0),
                c + cv::Vec3f(-hw,  hh, 0),
            };

            cv::Point2f src[4] = {
                {0, 0},
                {static_cast<float>(p.texture.cols - 1), 0},
                {static_cast<float>(p.texture.cols - 1), static_cast<float>(p.texture.rows - 1)},
                {0, static_cast<float>(p.texture.rows - 1)},
            };
            cv::Point2f dst[4];
            for (int k = 0; k < 4; ++k)
                dst[k] = project(corners_w[k], K, R_w2c, t_w2c);

            cv::Mat M = cv::getPerspectiveTransform(src, dst);

            // Warp into a temp canvas of the full frame size, then blend.
            cv::Mat warped(H, W, CV_8UC3, cv::Scalar(0, 0, 0));
            cv::Mat mask(p.texture.rows, p.texture.cols, CV_8UC1, cv::Scalar(255));
            cv::Mat warped_mask(H, W, CV_8UC1, cv::Scalar(0));
            cv::warpPerspective(p.texture, warped, M, cv::Size(W, H),
                                cv::INTER_LINEAR, cv::BORDER_TRANSPARENT);
            cv::warpPerspective(mask, warped_mask, M, cv::Size(W, H),
                                cv::INTER_NEAREST);

            // Focus highlight — a brief glow when this window becomes active.
            int rel = f - p.focus_start;
            if (rel >= 0 && rel < p.focus_len) {
                cv::Mat bright;
                warped.convertTo(bright, -1, 1.10, 12);
                bright.copyTo(frame, warped_mask);
            } else {
                warped.copyTo(frame, warped_mask);
            }
        }

        // Mouse cursor — moves between focused windows.
        // Pick the currently-focused panel; if none, idle near screen center.
        cv::Vec3f cursor_w(0, 0, 6.0f);
        bool clicking = false;
        for (size_t i = 0; i < panels.size(); ++i) {
            int rel = f - panels[i].focus_start;
            if (rel >= 0 && rel < panels[i].focus_len) {
                float u = static_cast<float>(rel) / panels[i].focus_len;
                cv::Vec3f drift(0.25f * std::sin(0.4f * t + i),
                                0.15f * std::cos(0.3f * t + i),
                                0.0f);
                cv::Vec3f c = panels[i].center + drift;
                // Sweep across the panel.
                cursor_w = c + cv::Vec3f(panels[i].size.width * (u - 0.5f) * 0.7f,
                                         panels[i].size.height * (0.5f - u) * 0.5f,
                                         0.0f);
                clicking = (rel % 30) < 6;
                break;
            }
        }
        cv::Point2f cursor_px = project(cursor_w, K, R_w2c, t_w2c);
        if (cursor_px.x > -20 && cursor_px.x < W + 20 &&
            cursor_px.y > -20 && cursor_px.y < H + 20) {
            draw_cursor(frame, cursor_px, clicking);
        }

        writer.write(frame);

        if (f % 30 == 0) {
            std::cout << "  frame " << f + 1 << "/" << N << "\n";
        }
    }

    writer.release();
    std::cout << "Wrote " << out_path << "\n";
    return 0;
}

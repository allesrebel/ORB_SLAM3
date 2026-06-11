// mono_topological_screencast.cc
//
// Topological place-graph SLAM for screencast video frames.
// Reuses ORB-SLAM3's ORBextractor and DBoW2 vocabulary; replaces the
// geometric back-end with a place graph.
//
// Usage:
//   mono_topological_screencast <vocab.txt> <settings.yaml> <frames_dir> <fps> [--out <dir>]
//
// Output (in <out>):
//   place_graph.json       Nodes + edges describing the topological map.
//   transitions.csv        Flat duplicate of edges.
//   place_keyframes/<id>.png    Representative frame for each place.
//   scores.csv             Per-frame DBoW2 score against current place (for tuning).

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

#include <opencv2/core/core.hpp>
#include <opencv2/imgcodecs.hpp>
#include <opencv2/imgproc.hpp>
#include <opencv2/calib3d.hpp>
#include <opencv2/features2d.hpp>

#include "ORBextractor.h"
#include "Thirdparty/DBoW2/DBoW2/FORB.h"
#include "Thirdparty/DBoW2/DBoW2/TemplatedVocabulary.h"

namespace fs = std::filesystem;

using OrbVocabulary =
    DBoW2::TemplatedVocabulary<DBoW2::FORB::TDescriptor, DBoW2::FORB>;

// -- thresholds (empirically tuned on VideoCUA Task A in Phase 3.3) -------
// DBoW2's score() with ORBvoc.txt on UI screenshots returns much higher
// values than typical (mostly 0.28-1.0 against representative frames).
// The "stay" mode for stable UI sits around 0.30-0.35; values above 0.40
// indicate strong similarity (early frames near representative). Anything
// below 0.30 indicates real visual change, so 0.40 is the working threshold
// to keep within-place noise from triggering births while still detecting
// real transitions.
static constexpr double TAU_SAME        = 0.40;
static constexpr double TAU_REVISIT     = 0.55;
static constexpr int    K_LEAVE_FRAMES  = 10;
static constexpr double SCORE_NORM_DENOM = 1.0;  // DBoW2 score is already in [0,1] for ORBvoc

// Optuna DSE parameters (Can be overridden via CLI)
static double HASH_SIM_THRESHOLD = 0.85;
static int AFFINE_MIN_INLIERS = 10;
static int TARGET_KEYPOINTS = 1000;
static int STATIC_TH = -1; // If > 0, disables PID

// Sub-project 2: Translation+scale-only RANSAC restriction.
// When enabled (RESTRICT_ROTATION=true), any candidate whose recovered
// rotation angle exceeds MAX_ROTATION_DEG is rejected.
// Controlled by CLI flag --restrict_rotation (default: off = full affine)
// or env var RESTRICT_ROTATION=1.
static bool RESTRICT_ROTATION = false;
static double MAX_ROTATION_DEG = 2.0;  // reject if |angle| > 2 degrees

static double normalize_score(double s) {
    double n = s / SCORE_NORM_DENOM;
    if (n < 0.0) return 0.0;
    if (n > 1.0) return 1.0;
    return n;
}

// Pixel Hashing function (Upgraded to Perceptual Hash for scrolling resilience)
static cv::Mat computeHash(const cv::Mat& img) {
    cv::Mat resized, float_img, dct_img, hash_mat;
    cv::resize(img, resized, cv::Size(32, 32));
    resized.convertTo(float_img, CV_32F);
    cv::dct(float_img, dct_img);
    cv::Mat dct_8x8 = dct_img(cv::Rect(0, 0, 8, 8)).clone();
    // Ignore DC term
    double m = (cv::sum(dct_8x8)[0] - dct_8x8.at<float>(0,0)) / 63.0;
    cv::compare(dct_8x8, m, hash_mat, cv::CMP_GT);
    return hash_mat;
}

static double compareHashes(const cv::Mat& h1, const cv::Mat& h2) {
    if (h1.empty() || h2.empty()) return 0.0;
    int diff = cv::countNonZero(h1 != h2);
    return 1.0 - (double)diff / (h1.total());
}

// Returns inlier count from RANSAC; also fills rotation_deg if not nullptr.
// If RESTRICT_ROTATION is set and |rotation| > MAX_ROTATION_DEG, returns -1
// (rejected by rotation test).
static int verifySpatialInliers(const std::vector<cv::KeyPoint>& kps1, const cv::Mat& desc1,
                                const std::vector<cv::KeyPoint>& kps2, const cv::Mat& desc2,
                                double* rotation_deg_out = nullptr) {
    if (desc1.empty() || desc2.empty()) return 0;

    cv::BFMatcher matcher(cv::NORM_HAMMING, true); // cross-check
    std::vector<cv::DMatch> matches;
    matcher.match(desc1, desc2, matches);

    // RANSAC Degeneracy Fallback: If not enough features (e.g. blank document), trust the Hash
    if ((int)matches.size() < 15) return AFFINE_MIN_INLIERS; // pretend pass

    std::vector<cv::Point2f> pts1, pts2;
    for (const auto& m : matches) {
        pts1.push_back(kps1[m.queryIdx].pt);
        pts2.push_back(kps2[m.trainIdx].pt);
    }

    // Use Affine verification (estimateAffinePartial2D = Sim2: tx,ty,cos,sin)
    std::vector<uchar> inliers;
    cv::Mat affine = cv::estimateAffinePartial2D(pts1, pts2, inliers, cv::RANSAC, 3.0);

    if (affine.empty()) return 0;

    int inlier_count = 0;
    for (uchar inl : inliers) { if (inl) inlier_count++; }

    if (RESTRICT_ROTATION) {
        // Recover rotation angle: M = s*[cos θ, -sin θ; sin θ, cos θ]
        // affine rows: [a00, a01, tx; a10, a11, ty]
        double a00 = affine.at<double>(0,0);
        double a10 = affine.at<double>(1,0);
        double angle_rad = std::atan2(a10, a00);
        double angle_deg = angle_rad * 180.0 / M_PI;
        if (rotation_deg_out) *rotation_deg_out = angle_deg;

        if (std::fabs(angle_deg) > MAX_ROTATION_DEG) {
            return -1; // rotation-rejected
        }
    } else {
        if (rotation_deg_out) *rotation_deg_out = 0.0;
    }

    return inlier_count;
}

static bool verifySpatial(const std::vector<cv::KeyPoint>& kps1, const cv::Mat& desc1,
                          const std::vector<cv::KeyPoint>& kps2, const cv::Mat& desc2) {
    int inliers = verifySpatialInliers(kps1, desc1, kps2, desc2);
    if (inliers < 0) return false; // rotation rejected
    return inliers >= AFFINE_MIN_INLIERS;
}

struct Place {
    int id;
    int representative_frame_idx;
    int frame_start;
    int frame_end;
    DBoW2::BowVector representative_bow;
    std::string representative_image_path;
    std::vector<cv::KeyPoint> kps;
    cv::Mat desc;
    cv::Mat hash;
};

struct Edge {
    int from_place_id;
    int to_place_id;
    int frame_idx;
    double depth;       // 1 - normalize(score(bow_from, bow_to)) ∈ [0,1]
    std::string type;   // "new" | "revisit"
};

static std::vector<cv::Mat> descriptors_to_vec(const cv::Mat& desc) {
    std::vector<cv::Mat> out;
    out.reserve(desc.rows);
    for (int i = 0; i < desc.rows; ++i) out.push_back(desc.row(i));
    return out;
}

static std::vector<std::string> list_frames(const std::string& dir) {
    std::vector<std::string> paths;
    for (const auto& e : fs::directory_iterator(dir)) {
        if (!e.is_regular_file()) continue;
        const auto p = e.path();
        const auto ext = p.extension().string();
        if (ext == ".png" || ext == ".jpg" || ext == ".jpeg" ||
            ext == ".PNG" || ext == ".JPG" || ext == ".JPEG") {
            paths.push_back(p.string());
        }
    }
    std::sort(paths.begin(), paths.end());
    return paths;
}

static int read_int(cv::FileStorage& fs_, const std::string& k, int def) {
    auto n = fs_[k];
    return n.empty() ? def : (int)n;
}

static float read_float(cv::FileStorage& fs_, const std::string& k, float def) {
    auto n = fs_[k];
    return n.empty() ? def : (float)n;
}

int main(int argc, char** argv) {
    if (argc < 5) {
        std::cerr << "Usage: mono_topological_screencast <vocab> <yaml> "
                     "<frames_dir> <fps> [--out <dir>]\n";
        return 1;
    }
    const std::string vocab_path  = argv[1];
    const std::string yaml_path   = argv[2];
    const std::string frames_dir  = argv[3];
    const double fps              = std::stod(argv[4]);

    // Check env var for rotation restriction
    {
        const char* env_rr = std::getenv("RESTRICT_ROTATION");
        if (env_rr && std::string(env_rr) == "1") RESTRICT_ROTATION = true;
    }

    std::string out_dir = ".";
    for (int i = 5; i + 1 < argc; ++i) {
        if (std::string(argv[i]) == "--out") out_dir = argv[i + 1];
        if (std::string(argv[i]) == "--target_kp") TARGET_KEYPOINTS = std::stoi(argv[i+1]);
        if (std::string(argv[i]) == "--hash_th") HASH_SIM_THRESHOLD = std::stod(argv[i+1]);
        if (std::string(argv[i]) == "--affine_min") AFFINE_MIN_INLIERS = std::stoi(argv[i+1]);
        if (std::string(argv[i]) == "--static_th") STATIC_TH = std::stoi(argv[i+1]);
        if (std::string(argv[i]) == "--restrict_rotation") RESTRICT_ROTATION = (std::stoi(argv[i+1]) != 0);
        if (std::string(argv[i]) == "--max_rot_deg") MAX_ROTATION_DEG = std::stod(argv[i+1]);
    }
    // Also check if it's a standalone flag (no value needed)
    for (int i = 5; i < argc; ++i) {
        if (std::string(argv[i]) == "--restrict_rotation") RESTRICT_ROTATION = true;
    }
    std::cout << "RANSAC mode: " << (RESTRICT_ROTATION ? "translation+scale only (max_rot=" + std::to_string(MAX_ROTATION_DEG) + " deg)" : "full affine (rotation allowed)") << "\n";
    fs::create_directories(out_dir);
    fs::create_directories(out_dir + "/place_keyframes");
    fs::create_directories(out_dir + "/debug_keypoints");

    // -- load vocabulary ----------------------------------------------------
    std::cout << "Loading vocabulary: " << vocab_path << std::endl;
    OrbVocabulary vocab;
    if (!vocab.loadFromTextFile(vocab_path)) {
        std::cerr << "Failed to load vocabulary: " << vocab_path << std::endl;
        return 2;
    }
    std::cout << "Vocabulary: " << vocab.size() << " words" << std::endl;

    // -- load YAML for ORB extractor params ---------------------------------
    cv::FileStorage settings(yaml_path, cv::FileStorage::READ);
    if (!settings.isOpened()) {
        std::cerr << "Failed to open settings: " << yaml_path << std::endl;
        return 2;
    }
    int   nFeatures   = read_int  (settings, "ORBextractor.nFeatures", 1500);
    float scaleFactor = read_float(settings, "ORBextractor.scaleFactor", 1.2f);
    int   nLevels     = read_int  (settings, "ORBextractor.nLevels", 8);
    int   iniThFAST   = read_int  (settings, "ORBextractor.iniThFAST", 12);
    int   minThFAST   = read_int  (settings, "ORBextractor.minThFAST", 4);

    // Fork's ORBextractor takes 4 extra extension args after the standard 5;
    // we keep all extensions OFF for plain topological mapping.
    ORB_SLAM3::ORBextractor extractor(nFeatures, scaleFactor, nLevels,
                                      iniThFAST, minThFAST,
                                      /*enableFOV=*/false,
                                      /*maskHeight=*/0, /*maskWidth=*/0,
                                      /*enableOasis=*/false);

    // -- list frames --------------------------------------------------------
    auto frame_paths = list_frames(frames_dir);
    std::cout << "Frames found: " << frame_paths.size() << std::endl;
    if (frame_paths.size() < 10) {
        std::cerr << "Too few frames (" << frame_paths.size() << ") — aborting"
                  << std::endl;
        return 3;
    }

    // -- main loop ----------------------------------------------------------
    std::vector<Place> places;
    std::vector<Edge>  edges;
    int current_place_idx = -1;
    int leaving_counter   = 0;

    std::ofstream score_log(out_dir + "/scores.csv");
    score_log << "frame,score_curr\n";

    std::ofstream kp_stats(out_dir + "/keypoint_stats.csv");
    kp_stats << "frame,count,min_x,max_x,min_y,max_y,var_x,var_y,min_th\n";

    int ablation_total_candidates = 0;
    int ablation_rejected_by_hash = 0;
    int ablation_rejected_by_ransac = 0;
    int ablation_rejected_by_rotation = 0;

    auto t0 = std::chrono::steady_clock::now();

    // PID Controller State for Adaptive Features
    int target_keypoints = TARGET_KEYPOINTS;
    float smoothed_kp = (float)TARGET_KEYPOINTS;
    float integral_error = 0;
    float prev_error = 0;
    float Kp = 0.005f, Ki = 0.001f, Kd = 0.001f;

    for (size_t i = 0; i < frame_paths.size(); ++i) {
        cv::Mat img = cv::imread(frame_paths[i], cv::IMREAD_GRAYSCALE);
        if (img.empty()) {
            std::cerr << "Skip unreadable frame: " << frame_paths[i] << std::endl;
            continue;
        }

        std::vector<cv::KeyPoint> kps;
        cv::Mat desc;
        std::vector<int> lapping_area = {0, 0};
        
        extractor(img, cv::Mat(), kps, desc, lapping_area);

        int current_minTh = extractor.getMinThFAST();
        int new_minTh = current_minTh;
        
        if (STATIC_TH > 0) {
            new_minTh = STATIC_TH;
        } else {
            // PID update with EMA Damping
            int kp_count = kps.size();
            smoothed_kp = 0.8f * smoothed_kp + 0.2f * kp_count;
            
            float error = target_keypoints - smoothed_kp;
            integral_error += error;
            float derivative = error - prev_error;
            float adjustment = Kp * error + Ki * integral_error + Kd * derivative;
            prev_error = error;
            
            // Clamp adjustment derivative to prevent wild oscillations
            if (adjustment > 2.0f) adjustment = 2.0f;
            if (adjustment < -2.0f) adjustment = -2.0f;
            
            // If we have too few features (error > 0), adjustment is positive, we want to DECREASE threshold.
            // So we subtract the adjustment from the threshold.
            new_minTh = current_minTh - std::round(adjustment);
            
            // Bound the threshold to sane limits [1, 20]
            if (new_minTh < 1) new_minTh = 1;
            if (new_minTh > 20) new_minTh = 20;
        }
        
        extractor.setMinThFAST(new_minTh);

        if (desc.empty()) {
            score_log << i << ",0\n";
            kp_stats << i << ",0,0,0,0,0,0,0," << current_minTh << "\n";
            ++leaving_counter;
            continue;
        }

        // --- DEBUG INSTRUMENTATION ---
        cv::Mat img_kps;
        cv::drawKeypoints(img, kps, img_kps, cv::Scalar::all(-1), cv::DrawMatchesFlags::DEFAULT);
        std::ostringstream kp_img_name;
        kp_img_name << out_dir << "/debug_keypoints/frame_" << std::setw(5) << std::setfill('0') << i << ".png";
        cv::imwrite(kp_img_name.str(), img_kps);

        double sum_x = 0, sum_y = 0;
        double min_x = 1e9, max_x = -1e9, min_y = 1e9, max_y = -1e9;
        for (const auto& kp : kps) {
            sum_x += kp.pt.x;
            sum_y += kp.pt.y;
            if (kp.pt.x < min_x) min_x = kp.pt.x;
            if (kp.pt.x > max_x) max_x = kp.pt.x;
            if (kp.pt.y < min_y) min_y = kp.pt.y;
            if (kp.pt.y > max_y) max_y = kp.pt.y;
        }
        double mean_x = sum_x / kps.size();
        double mean_y = sum_y / kps.size();
        double var_x = 0, var_y = 0;
        for (const auto& kp : kps) {
            var_x += (kp.pt.x - mean_x) * (kp.pt.x - mean_x);
            var_y += (kp.pt.y - mean_y) * (kp.pt.y - mean_y);
        }
        var_x /= kps.size();
        var_y /= kps.size();

        kp_stats << i << "," << kps.size() << ","
                 << min_x << "," << max_x << ","
                 << min_y << "," << max_y << ","
                 << var_x << "," << var_y << "," << current_minTh << "\n";        // -----------------------------

        DBoW2::BowVector  bow_t;
        DBoW2::FeatureVector fv_t;
        vocab.transform(descriptors_to_vec(desc), bow_t, fv_t, 4);

        cv::Mat curr_hash = computeHash(img);

        if (current_place_idx < 0) {
            // cold start — birth place 0
            Place p;
            p.id = (int)places.size();
            p.representative_frame_idx = (int)i;
            p.frame_start = (int)i;
            p.frame_end   = (int)i;
            p.representative_bow = bow_t;
            std::ostringstream ip;
            ip << out_dir << "/place_keyframes/" << p.id << ".png";
            cv::imwrite(ip.str(), cv::imread(frame_paths[i]));
            p.representative_image_path = ip.str();
            p.kps = kps;
            p.desc = desc;
            p.hash = curr_hash;
            places.push_back(p);
            current_place_idx = p.id;
            score_log << i << ",1\n";
            continue;
        }

        double score_curr = vocab.score(bow_t,
            places[current_place_idx].representative_bow);
        score_log << i << "," << std::fixed << std::setprecision(6)
                  << score_curr << "\n";

        double hash_sim_curr = compareHashes(curr_hash, places[current_place_idx].hash);

        bool is_same = false;
        if (score_curr >= TAU_SAME && hash_sim_curr >= HASH_SIM_THRESHOLD) {
            // Further verify spatially to prevent false positives from rearranged UI elements
            is_same = verifySpatial(kps, desc, places[current_place_idx].kps, places[current_place_idx].desc);
        }

        if (is_same) {
            places[current_place_idx].frame_end = (int)i;
            leaving_counter = 0;
            continue;
        }

        // possibly leaving — check revisit candidates
        int    best_revisit = -1;
        double best_score   = 0.0;
        for (size_t p = 0; p < places.size(); ++p) {
            if ((int)p == current_place_idx) continue;
            double s = vocab.score(bow_t, places[p].representative_bow);
            if (s >= TAU_REVISIT) {
                ablation_total_candidates++;
                double hs = compareHashes(curr_hash, places[p].hash);
                if (hs >= HASH_SIM_THRESHOLD) {
                    int inliers = verifySpatialInliers(kps, desc, places[p].kps, places[p].desc);
                    if (inliers < 0) {
                        // rejected by rotation constraint
                        ablation_rejected_by_rotation++;
                    } else if (inliers >= AFFINE_MIN_INLIERS) {
                        if (s > best_score) {
                            best_score = s;
                            best_revisit = (int)p;
                        }
                    } else {
                        ablation_rejected_by_ransac++;
                    }
                } else {
                    ablation_rejected_by_hash++;
                }
            }
        }

        if (best_revisit >= 0) {
            Edge e;
            e.from_place_id = current_place_idx;
            e.to_place_id   = best_revisit;
            e.frame_idx     = (int)i;
            e.depth         = 1.0 - normalize_score(best_score);
            e.type          = "revisit";
            edges.push_back(e);
            current_place_idx = best_revisit;
            places[best_revisit].frame_end = (int)i;
            leaving_counter = 0;
            continue;
        }

        ++leaving_counter;
        if (leaving_counter >= K_LEAVE_FRAMES) {
            Place new_p;
            new_p.id = (int)places.size();
            new_p.representative_frame_idx = (int)i;
            new_p.frame_start = (int)i;
            new_p.frame_end   = (int)i;
            new_p.representative_bow = bow_t;
            std::ostringstream ip;
            ip << out_dir << "/place_keyframes/" << new_p.id << ".png";
            cv::imwrite(ip.str(), cv::imread(frame_paths[i]));
            new_p.representative_image_path = ip.str();
            new_p.kps = kps;
            new_p.desc = desc;
            new_p.hash = curr_hash;

            double d_score = vocab.score(
                places[current_place_idx].representative_bow,
                new_p.representative_bow);

            Edge e;
            e.from_place_id = current_place_idx;
            e.to_place_id   = new_p.id;
            e.frame_idx     = (int)i;
            e.depth         = 1.0 - normalize_score(d_score);
            e.type          = "new";
            edges.push_back(e);

            places.push_back(new_p);
            current_place_idx = new_p.id;
            leaving_counter = 0;
        }
    }

    auto t1 = std::chrono::steady_clock::now();
    double secs = std::chrono::duration<double>(t1 - t0).count();

    // -- write outputs ------------------------------------------------------
    std::ofstream json(out_dir + "/place_graph.json");
    json << "{\n";
    json << "  \"fps\": " << fps << ",\n";
    json << "  \"n_frames\": " << frame_paths.size() << ",\n";
    json << "  \"places\": [\n";
    for (size_t i = 0; i < places.size(); ++i) {
        json << "    {\"id\": " << places[i].id
             << ", \"representative_frame\": " << places[i].representative_frame_idx
             << ", \"frame_range\": [" << places[i].frame_start
             << ", " << places[i].frame_end << "]"
             << ", \"keyframe_image\": \"place_keyframes/"
             << places[i].id << ".png\"}";
        if (i + 1 < places.size()) json << ",";
        json << "\n";
    }
    json << "  ],\n";
    json << "  \"edges\": [\n";
    for (size_t i = 0; i < edges.size(); ++i) {
        json << "    {\"from\": " << edges[i].from_place_id
             << ", \"to\": " << edges[i].to_place_id
             << ", \"frame\": " << edges[i].frame_idx
             << ", \"depth\": " << std::fixed << std::setprecision(4)
                                << edges[i].depth
             << ", \"type\": \"" << edges[i].type << "\"}";
        if (i + 1 < edges.size()) json << ",";
        json << "\n";
    }
    json << "  ]\n}\n";

    std::ofstream ablation(out_dir + "/ablation_stats.json");
    ablation << "{\n";
    ablation << "  \"total_revisit_candidates\": " << ablation_total_candidates << ",\n";
    ablation << "  \"rejected_by_hash\": " << ablation_rejected_by_hash << ",\n";
    ablation << "  \"rejected_by_ransac\": " << ablation_rejected_by_ransac << ",\n";
    ablation << "  \"rejected_by_rotation\": " << ablation_rejected_by_rotation << ",\n";
    ablation << "  \"restrict_rotation_mode\": " << (RESTRICT_ROTATION ? "true" : "false") << ",\n";
    ablation << "  \"max_rotation_deg\": " << MAX_ROTATION_DEG << "\n";
    ablation << "}\n";

    std::ofstream csv(out_dir + "/transitions.csv");
    csv << "from,to,frame,depth,type\n";
    for (const auto& e : edges) {
        csv << e.from_place_id << "," << e.to_place_id << ","
            << e.frame_idx << "," << std::fixed << std::setprecision(4)
            << e.depth << "," << e.type << "\n";
    }

    std::cout << "\n=== mono_topological_screencast summary ===\n";
    std::cout << "Frames processed:    " << frame_paths.size() << "\n";
    std::cout << "Places identified:   " << places.size() << "\n";
    std::cout << "Edges (transitions): " << edges.size() << "\n";
    std::cout << "Wall time:           " << secs << " s ("
              << (frame_paths.size() / std::max(secs, 1e-6)) << " fps)\n";
    return 0;
}

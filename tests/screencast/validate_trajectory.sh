#!/usr/bin/env bash
# validate_trajectory.sh — sanity-check a TUM-format keyframe trajectory.
#
# Usage:
#   validate_trajectory.sh <traj.txt> [min_keyframes] [min_path_length]
#
# Format expected (one keyframe per line):
#   timestamp tx ty tz qx qy qz qw
#
# Exits 0 if the trajectory is sane, non-zero otherwise. Prints the
# per-axis ranges, total path length and quaternion-norm extremes so a
# human reviewer can also eyeball it.

set -euo pipefail

TRAJ="${1:-}"
MIN_KFS="${2:-5}"
MIN_PATH_LEN="${3:-0.001}"

if [[ -z "$TRAJ" || ! -f "$TRAJ" ]]; then
    echo "validate_trajectory: missing or empty trajectory file: $TRAJ" >&2
    exit 1
fi

awk -v MIN_KFS="$MIN_KFS" -v MIN_PATH_LEN="$MIN_PATH_LEN" '
BEGIN {
    n = 0; bad = 0;
    last_t = -1e300;
    pathlen = 0;
    px = py = pz = 0;
    have_prev = 0;
    qnorm_min = 1e30; qnorm_max = -1e30;
}
NF == 0 { next }
{
    if (NF != 8) {
        printf("  malformed line %d (NF=%d): %s\n", NR, NF, $0); bad++;
        next;
    }
    t  = $1+0;  tx = $2+0;  ty = $3+0;  tz = $4+0;
    qx = $5+0;  qy = $6+0;  qz = $7+0;  qw = $8+0;
    qn = sqrt(qx*qx + qy*qy + qz*qz + qw*qw);
    if (qn < qnorm_min) qnorm_min = qn;
    if (qn > qnorm_max) qnorm_max = qn;
    if (t < last_t - 1e-9) {
        printf("  timestamp regression at line %d: %.9f < %.9f\n", NR, t, last_t);
        bad++;
    }
    last_t = t;
    if (n == 0) {
        xmin = xmax = tx;  ymin = ymax = ty;  zmin = zmax = tz;
    } else {
        if (tx < xmin) xmin = tx; if (tx > xmax) xmax = tx;
        if (ty < ymin) ymin = ty; if (ty > ymax) ymax = ty;
        if (tz < zmin) zmin = tz; if (tz > zmax) zmax = tz;
    }
    if (have_prev) {
        dx = tx - px; dy = ty - py; dz = tz - pz;
        pathlen += sqrt(dx*dx + dy*dy + dz*dz);
    }
    px = tx; py = ty; pz = tz;
    have_prev = 1;
    n++;
}
END {
    span_x = (n>0) ? xmax - xmin : 0;
    span_y = (n>0) ? ymax - ymin : 0;
    span_z = (n>0) ? zmax - zmin : 0;
    span_max = span_x;
    if (span_y > span_max) span_max = span_y;
    if (span_z > span_max) span_max = span_z;

    printf("  keyframes:        %d\n", n);
    printf("  malformed lines:  %d\n", bad);
    if (n > 0) {
        printf("  x range:          [%.6f, %.6f]   span=%.6f\n", xmin, xmax, span_x);
        printf("  y range:          [%.6f, %.6f]   span=%.6f\n", ymin, ymax, span_y);
        printf("  z range:          [%.6f, %.6f]   span=%.6f\n", zmin, zmax, span_z);
        printf("  path length:     %.6f\n", pathlen);
        printf("  quaternion norm: [%.6f, %.6f]\n", qnorm_min, qnorm_max);
    }

    fail = 0;
    if (n < MIN_KFS) {
        printf("  FAIL: only %d keyframes (need >= %d)\n", n, MIN_KFS); fail=1;
    }
    if (bad > 0) {
        printf("  FAIL: %d malformed lines\n", bad); fail=1;
    }
    if (n > 0 && span_max < 1e-9) {
        printf("  FAIL: trajectory is stationary (all-zero translation)\n"); fail=1;
    }
    if (n > 0 && pathlen < MIN_PATH_LEN) {
        printf("  FAIL: path length %.6f below minimum %.6f\n", pathlen, MIN_PATH_LEN); fail=1;
    }
    if (n > 1 && (qnorm_min < 0.99 || qnorm_max > 1.01)) {
        printf("  FAIL: non-unit quaternion (norm range %.6f .. %.6f)\n",
               qnorm_min, qnorm_max); fail=1;
    }
    exit(fail);
}
' "$TRAJ"

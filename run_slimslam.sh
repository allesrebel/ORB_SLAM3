#!/usr/bin/env bash
###############################################################################
# run_slimslam_all.sh
#
# Runs ORB-SLAM3 + SlimSLAM over every control file found in
#   ./slimslam_control_files/
#
# For each control file we:
#   • create a temporary YAML that hard-codes SlimSLAM.ControlFile
#   • work out the right EuRoC sequence/timestamp file automatically
#   • repeat the run NUM_RUNS times (useful for time-noise statistics)
#   • archive logs + *_Stats.txt + optional map-files into a dated folder
#
# Author: (your name) – 2025-06-04
###############################################################################
set -euo pipefail

#####################################  CONFIG  ################################
BASE_CFG="./Examples/Stereo-Inertial/EuRoC_slimslam_deadlines.yaml"
CONTROL_DIR="./slimslam_control_files"
VOC="./Vocabulary/ORBvoc.txt"
EXE="./Examples/Stereo-Inertial/stereo_inertial_euroc"
DATA_ROOT="./Datasets/EuRoc"
TS_ROOT="./Examples/Stereo-Inertial/EuRoC_TimeStamps"

NUM_RUNS=10              # ← change if you need fewer / more repetitions
###############################################################################

DATE_TAG=$(date +'%Y-%m-%d_%H-%M-%S')

# helper ──────────────────────────────────────────────────────────────────────
make_temp_cfg() {
  local tmp_cfg=$1  control_path=$2
  cp "$BASE_CFG" "$tmp_cfg"

  if grep -qE '^\s*SlimSLAM\.ControlFile:' "$tmp_cfg"; then
    sed -i "s|^\s*SlimSLAM\.ControlFile:.*|SlimSLAM.ControlFile: \"${control_path}\"|" "$tmp_cfg"
  else
    printf '\nSlimSLAM.ControlFile: "%s"\n' "$control_path" >> "$tmp_cfg"
  fi
}

dataset_id_from_tag() {
  local tag=$1            # e.g. "MH_01_easy"  |  "V2_03_difficult"
  if [[ $tag =~ ^MH_([0-9]{2})_ ]]; then           # → MH01
    echo "MH${BASH_REMATCH[1]}"
  elif [[ $tag =~ ^V([0-9])_([0-9]{2})_ ]]; then   # → V101 … V203
    echo "V${BASH_REMATCH[1]}${BASH_REMATCH[2]}"
  else                                             # unknown tag
    echo ""
  fi
}

dataset_core_from_tag() {
  # "MH_01_easy"  →  "MH_01"
  # "V2_03_medium"→  "V2_03"
  echo "$1" | cut -d'_' -f1-2
}

###############################################################################
for ctrl_path in "${CONTROL_DIR}"/*_control.txt; do
  [[ -e "$ctrl_path" ]] || { echo "No control files found – aborting."; exit 1; }

  ctrl_name=$(basename "$ctrl_path")              # MH_01_easy_control.txt
  tag=${ctrl_name%_control.txt}                   # MH_01_easy
  ts_id=$(dataset_id_from_tag "$tag")             # MH01
  core=$(dataset_core_from_tag "$tag")            # MH_01
  [[ -n $ts_id ]] || { echo "Unrecognised tag '$tag' – skipping."; continue; }

  echo "───────────────────────────────────────────────────────────────────"
  echo "▶ Dataset tag : $tag"
  echo "▶ Timestamp   : ${TS_ROOT}/${ts_id}.txt"
  echo "▶ Control file: $ctrl_path"
  echo

  for ((run=1; run<=NUM_RUNS; run++)); do
    tmp_cfg=$(mktemp /tmp/slimslam_cfg_XXXX.yaml)
    make_temp_cfg "$tmp_cfg" "$ctrl_path"

    log="cout_slimslam_${tag}_${run}_${DATE_TAG}.log"
    result_dir="${DATE_TAG}_slimslam_${tag}_run_${run}"
    mkdir -p "$result_dir"

    echo "  • run #${run}  →  ${result_dir}"

    "$EXE" "$VOC" "$tmp_cfg" \
      "${DATA_ROOT}/${core}"* \
      "${TS_ROOT}/${ts_id}.txt" \
      "dataset-${tag}_run${run}" \
      >"$log" 2>&1

    # gather artifacts --------------------------------------------------------
    mv "$log"                                               "$result_dir"/
    for f in LocalMapTimeStats.txt ExecMean.txt LBA_Stats.txt \
             TrackingTimeStats.txt SessionInfo.txt           \
             map_points.csv cellManager.txt                  \
             f_dataset-* kf_dataset-*; do
      [[ -f $f ]] && mv "$f" "$result_dir"/
    done

    rm -f "$tmp_cfg"
  done
done

echo "✓ All SlimSLAM runs finished – results live under *_slimslam_* folders."

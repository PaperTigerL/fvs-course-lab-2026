#!/usr/bin/env bash
# Supplementary experiment: GateANN Low-bucket L scan, repeated REPEATS times.
#
# Purpose: decide whether the Low-bucket recall collapse is "not enough search
# budget" or "structural fragmentation of the filtered graph".
#
# Usage (inside WSL):
#   cd /home/user/fvs-course-lab && bash scripts/run_supp_low_L.sh
#
# Optional overrides:
#   REPEATS=3 L_LIST="320 640 1280 2560" bash scripts/run_supp_low_L.sh
#
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

REPEATS="${REPEATS:-3}"
L_LIST="${L_LIST:-320 640 1280 2560}"
RUN_TAG="${RUN_TAG:-supp_low_Lscan_3runs}"
BUCKET="${BUCKET:-low}"
SYSTEM_REPO="${SYSTEM_REPO:-$repo_root/systems/GateANN-public}"
DATASET_ROOT="${DATASET_ROOT:-$repo_root/datasets/yfcc_course_v1}"
RUN_ROOT="${RUN_ROOT:-$repo_root/course_runs}"

cd "$repo_root"
# shellcheck disable=SC1091
source "$repo_root/config/experiments.env"

echo "=== Supp Low-bucket L scan ==="
echo "repeats=$REPEATS  L=[$L_LIST]  bucket=$BUCKET  tag=$RUN_TAG"
echo "threads=$FVS_THREADS beamwidth=$FVS_BEAMWIDTH k=$FVS_TOPK"

python3 "$repo_root/adapters/gateann_adapter.py" doctor \
  --repo "$SYSTEM_REPO" --dataset-root "$DATASET_ROOT" --tier formal

for r in $(seq 1 "$REPEATS"); do
  run_id="${RUN_TAG}_r${r}"
  echo "=== repeat $r/$REPEATS : $run_id ==="
  # shellcheck disable=SC2086
  python3 "$repo_root/adapters/gateann_adapter.py" search \
    --repo "$SYSTEM_REPO" \
    --dataset-root "$DATASET_ROOT" \
    --tier formal \
    --run-root "$RUN_ROOT" \
    --threads "$FVS_THREADS" \
    --beamwidth "$FVS_BEAMWIDTH" \
    --k "$FVS_TOPK" \
    --bucket "$BUCKET" \
    --L $L_LIST \
    --full-adj-neighbors 32 \
    --run-id "$run_id"
done

python3 "$repo_root/scripts/collect_supp_low_L.py" \
  --run-root "$RUN_ROOT" \
  --bucket "$BUCKET" \
  --tag "$RUN_TAG" \
  --repeats "$REPEATS"

echo "DONE. Aggregated CSV:"
echo "  $RUN_ROOT/results/gateann/formal_1000000/$BUCKET/$RUN_TAG/results_aggregated.csv"

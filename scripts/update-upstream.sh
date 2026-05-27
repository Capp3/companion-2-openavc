#!/usr/bin/env bash
# Refresh the vendored open-avc/openavc-drivers snapshot.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENDOR_DIR="${ROOT}/c2o/vendored/openavc_drivers"
TEMP_DIR="$(mktemp -d)"
REPO_URL="https://github.com/open-avc/openavc-drivers.git"

cleanup() {
  rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

echo "Cloning ${REPO_URL} ..."
git clone --depth 1 "${REPO_URL}" "${TEMP_DIR}/openavc-drivers"

COMMIT="$(git -C "${TEMP_DIR}/openavc-drivers" rev-parse HEAD)"
echo "Upstream commit: ${COMMIT}"

mkdir -p "${VENDOR_DIR}/scripts"
cp "${TEMP_DIR}/openavc-drivers/scripts/build_index.py" "${VENDOR_DIR}/scripts/"
cp "${TEMP_DIR}/openavc-drivers/manufacturers.json" "${VENDOR_DIR}/"
cp "${TEMP_DIR}/openavc-drivers/AGENTS.md" "${VENDOR_DIR}/"
echo "${COMMIT}" > "${VENDOR_DIR}/VENDOR_COMMIT"

echo "Vendor snapshot updated at ${VENDOR_DIR}"

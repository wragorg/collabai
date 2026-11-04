#!/bin/sh
# collabai installer. Download, inspect, then run — never blind-pipe.
# Usage: curl -fsSL https://github.com/wragorg/collabai/releases/latest/download/install.sh -o install.sh
#        sh install.sh [--version X.Y.Z]
set -eu

OWNER="${COLLABAI_OWNER:-wragorg}"
VERSION="${COLLABAI_VERSION:-2.0.0}"
PREFIX="${HOME}/.local"
BIN="${PREFIX}/bin/collabai"

usage() {
  echo "usage: sh install.sh [--version X.Y.Z]" >&2
}

while [ $# -gt 0 ]; do
  case "$1" in
    --version)
      VERSION="${2:-}"
      [ -n "${VERSION}" ] || { usage; exit 1; }
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      VERSION="$1"
      shift
      ;;
  esac
done

SRC="${PREFIX}/share/collabai-${VERSION}"

need() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing: $1" >&2; exit 1; }
}

need python3
need curl

if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "python >= 3.11 required (found: $(python3 -c 'import sys; print(f"{sys.version_info[0]}.{sys.version_info[1]}")'))" >&2
  exit 1
fi

if [ -z "${OWNER}" ] || [ "${OWNER}" = "<owner>" ]; then
  echo "release owner is not configured: set COLLABAI_OWNER=wragorg and re-run." >&2
  echo "This is YOU, the maintainer who publishes collabai releases on GitHub;" >&2
  echo "the download URL is https://github.com/wragorg/collabai/releases/..." >&2
  echo "Tool users do not change this; they only inspect and run this script." >&2
  exit 1
fi

URL="https://github.com/${OWNER}/collabai/releases/download/v${VERSION}/collabai-${VERSION}.tar.gz"
case "${URL}" in
  https://*) ;;
  *) echo "refusing non-HTTPS URL" >&2; exit 1 ;;
esac

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT
echo "downloading ${URL}"
curl --proto '=https' --tlsv1.2 -fsSL "${URL}" -o "${TMP}/collabai.tar.gz"
echo "downloading ${URL}.sha256"
curl --proto '=https' --tlsv1.2 -fsSL "${URL}.sha256" -o "${TMP}/collabai.tar.gz.sha256"

echo "verifying checksum"
# Compare hashes directly: the .sha256 names the release file
# (collabai-<v>.tar.gz), not our temp name, so `sha256sum -c` would miss it.
WANT="$(awk '{print $1}' "${TMP}/collabai.tar.gz.sha256" | tr 'A-F' 'a-f')"
case "${WANT}" in
  *[!0-9a-f]*|"") echo "checksum file has no sha256 digest" >&2; exit 1 ;;
esac
[ "${#WANT}" -eq 64 ] || { echo "checksum file has no sha256 digest" >&2; exit 1; }
if command -v sha256sum >/dev/null 2>&1; then
  GOT="$(sha256sum "${TMP}/collabai.tar.gz" | awk '{print $1}')"
elif command -v shasum >/dev/null 2>&1; then
  GOT="$(shasum -a 256 "${TMP}/collabai.tar.gz" | awk '{print $1}')"
else
  GOT="$(python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' "${TMP}/collabai.tar.gz")"
fi
GOT="$(printf '%s' "${GOT}" | tr 'A-F' 'a-f')"
if [ "${GOT}" != "${WANT}" ]; then
  echo "checksum mismatch: got ${GOT} want ${WANT}" >&2
  exit 1
fi
echo "checksum ok"

mkdir -p "${SRC}"
tar -xzf "${TMP}/collabai.tar.gz" -C "${SRC}"
if [ ! -f "${SRC}/collabai/__main__.py" ]; then
  echo "tarball layout wrong: ${SRC}/collabai/__main__.py missing" >&2
  exit 1
fi
mkdir -p "${PREFIX}/bin"
printf '#!/bin/sh\nPYTHONPATH="%s:${PYTHONPATH:-}" exec python3 -m collabai "$@"\n' "${SRC}" > "${BIN}"
chmod +x "${BIN}"
echo "installed to ${BIN}. ensure ${PREFIX}/bin is on PATH."
"${BIN}" --version

# Optional Meta AI key. Skipped without a terminal. Stored only by
# `collabai --meta-key` (hidden prompt, ~/.config/collabai/meta.key 0600),
# never in a repo or in .collabai/. Blank answer there skips it.
if [ -t 0 ]; then
  echo "optional: add a Meta API key for AI extras (blank skips; model meta-spark-1.3 will be used)"
  "${BIN}" --meta-key || echo "note: no Meta key stored; collabai works as before." >&2
fi

#!/bin/bash
#
# Build release tarball for aide-slideshow
#
# Creates a self-contained deployment package that includes aide_frame
# embedded in app/ directory (no git submodule dependency at runtime).
#
# Usage:
#   ./build-release.sh              # Build tarball (version from app/VERSION)
#   ./build-release.sh --clean      # Remove deploy/ and releases/ directories
#   ./build-release.sh 0.2          # Override version
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Project configuration
REPO_NAME="aide-slideshow"
DEPLOY_DIR="$SCRIPT_DIR/deploy"
RELEASES_DIR="$SCRIPT_DIR/releases"
AIDE_FRAME_SRC="$SCRIPT_DIR/aide-frame/python/aide_frame"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Handle --clean flag
if [ "$1" = "--clean" ]; then
    if [ -d "$DEPLOY_DIR" ]; then
        rm -rf "$DEPLOY_DIR"
        log_info "Removed deploy/ directory"
    fi
    if [ -d "$RELEASES_DIR" ]; then
        rm -rf "$RELEASES_DIR"
        log_info "Removed releases/ directory"
    fi
    [ ! -d "$DEPLOY_DIR" ] && [ ! -d "$RELEASES_DIR" ] && log_info "Nothing to clean"
    exit 0
fi

# Check that aide-frame submodule exists
if [ ! -d "$AIDE_FRAME_SRC" ]; then
    log_error "aide-frame submodule not found at $AIDE_FRAME_SRC"
    log_error "Run: git submodule update --init"
    exit 1
fi

# Get version
if [ -n "$1" ]; then
    VERSION="$1"
else
    VERSION=$(cat app/VERSION 2>/dev/null | tr -d '\n\r')
fi

if [ -z "$VERSION" ]; then
    log_error "No version specified and app/VERSION not found"
    exit 1
fi

log_info "Building release ${VERSION}..."

# Clean previous build
if [ -d "$DEPLOY_DIR" ]; then
    log_info "Cleaning previous build..."
    rm -rf "$DEPLOY_DIR"
fi

# Create deploy directory
mkdir -p "$DEPLOY_DIR"

# Copy app directory
log_info "Copying app/ directory..."
cp -r "$SCRIPT_DIR/app" "$DEPLOY_DIR/app"

# Copy aide_frame into app/
log_info "Embedding aide_frame into app/..."
cp -r "$AIDE_FRAME_SRC" "$DEPLOY_DIR/app/aide_frame"

# Copy aide-frame static assets
AIDE_FRAME_STATIC="$SCRIPT_DIR/aide-frame/static"
if [ -d "$AIDE_FRAME_STATIC" ]; then
    log_info "Copying aide-frame static assets..."
    cp -r "$AIDE_FRAME_STATIC" "$DEPLOY_DIR/app/aide_frame/static"
fi

# Copy config if exists
if [ -f "$SCRIPT_DIR/config.json" ]; then
    log_info "Copying config.json..."
    cp "$SCRIPT_DIR/config.json" "$DEPLOY_DIR/"
fi

# Copy other root files
for file in README.md LICENSE; do
    if [ -f "$SCRIPT_DIR/$file" ]; then
        cp "$SCRIPT_DIR/$file" "$DEPLOY_DIR/"
    fi
done

# Remove __pycache__ directories
log_info "Cleaning __pycache__ directories..."
find "$DEPLOY_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Show deploy structure
log_info "Build complete!"
echo ""
echo "Deploy directory structure:"
echo "  deploy/"
echo "  ├── app/"
echo "  │   ├── aide_frame/    (embedded)"
echo "  │   ├── slideshow.py"
echo "  │   └── ..."
if [ -f "$DEPLOY_DIR/config.json" ]; then
echo "  └── config.json"
fi
echo ""

# Show version and size
SIZE=$(du -sh "$DEPLOY_DIR" | cut -f1)
log_info "Version: $VERSION"
log_info "Deploy size: $SIZE"

# Create tarball
echo ""
mkdir -p "$RELEASES_DIR"
TARBALL_NAME="${REPO_NAME}-${VERSION}.tar.gz"
TARBALL_PATH="$RELEASES_DIR/$TARBALL_NAME"

log_info "Creating tarball: $TARBALL_NAME"
tar -czf "$TARBALL_PATH" -C "$DEPLOY_DIR" .

TARBALL_SIZE=$(du -sh "$TARBALL_PATH" | cut -f1)
log_info "Tarball size: $TARBALL_SIZE"
log_info "Created: releases/$TARBALL_NAME"

echo ""
echo "Next steps for release:"
echo "  1. git tag v$VERSION"
echo "  2. git push origin v$VERSION"
echo "  3. Create GitHub Release with tag v$VERSION"
echo "  4. Upload releases/$TARBALL_NAME as release asset"

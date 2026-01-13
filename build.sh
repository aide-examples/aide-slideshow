#!/bin/bash
#
# Build script for aide-slideshow deployment
#
# Creates a self-contained deployment package that includes aide_frame
# embedded in app/ directory (no git submodule dependency).
#
# Usage:
#   ./build.sh           # Build to deploy/ directory
#   ./build.sh --clean   # Remove deploy/ directory
#

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
DEPLOY_DIR="$SCRIPT_DIR/deploy"
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
    else
        log_info "deploy/ directory does not exist"
    fi
    exit 0
fi

# Check that aide-frame submodule exists
if [ ! -d "$AIDE_FRAME_SRC" ]; then
    log_error "aide-frame submodule not found at $AIDE_FRAME_SRC"
    log_error "Run: git submodule update --init"
    exit 1
fi

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

# Show result
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

# Show version
VERSION=$(cat "$DEPLOY_DIR/app/VERSION" 2>/dev/null || echo "unknown")
log_info "Version: $VERSION"

# Show size
SIZE=$(du -sh "$DEPLOY_DIR" | cut -f1)
log_info "Total size: $SIZE"

echo ""
log_info "To create tarball: tar -czf aide-slideshow-$VERSION.tar.gz -C deploy ."

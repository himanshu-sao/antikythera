#!/bin/bash
# Build and optionally push Antikythera Docker images
#
# Usage:
#   ./build-docker.sh              # Build locally
#   ./build-docker.sh push         # Build and push to Docker Hub
#   ./build-docker.sh push latest  # Push with specific tag
#
# Prerequisites:
#   - Docker logged in to Docker Hub (docker login)
#   - Repository: himanshusao/antikythera

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Configuration
DOCKERHUB_ORG="himanshusao"
BACKEND_IMAGE="$DOCKERHUB_ORG/antikythera"
UI_IMAGE="$DOCKERHUB_ORG/antikythera-ui"
TAG="${2:-latest}"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[OK]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

usage() {
    echo "Usage: $0 [push] [tag]"
    echo ""
    echo "Commands:"
    echo "  (none)     Build images locally"
    echo "  push       Build and push to Docker Hub"
    echo ""
    echo "Options:"
    echo "  tag        Image tag (default: latest)"
    echo ""
    echo "Examples:"
    echo "  $0                    # Build locally with :latest tag"
    echo "  $0 push               # Build and push with :latest tag"
    echo "  $0 push v1.2.3        # Build and push with :v1.2.3 tag"
}

build_image() {
    local image_name=$1
    local dockerfile=$2
    local tag=$3

    log_info "Building $image_name:$tag..."
    docker build -f "$dockerfile" -t "$image_name:$tag" "$PROJECT_ROOT"

    if [ "$4" = "push" ]; then
        log_info "Pushing $image_name:$tag..."
        docker push "$image_name:$tag"
        log_success "Pushed $image_name:$tag"
    else
        log_success "Built $image_name:$tag"
    fi
}

# Parse arguments
ACTION="${1:-build}"
TAG="${2:-latest}"

if [ "$1" = "-h" ] || [ "$1" = "--help" ]; then
    usage
    exit 0
fi

cd "$SCRIPT_DIR"

# Build Backend
log_info "=========================================="
log_info "Building Antikythera Backend"
log_info "=========================================="
build_image "$BACKEND_IMAGE" "Dockerfile" "$TAG" "$ACTION"

# Build Frontend
log_info "=========================================="
log_info "Building Antikythera UI"
log_info "=========================================="
build_image "$UI_IMAGE" "Dockerfile.ui" "$TAG" "$ACTION"

# Tag latest if different tag was specified
if [ "$TAG" != "latest" ] && [ "$ACTION" = "push" ]; then
    log_info "Tagging and pushing as latest..."
    docker tag "$BACKEND_IMAGE:$TAG" "$BACKEND_IMAGE:latest"
    docker push "$BACKEND_IMAGE:latest"
    docker tag "$UI_IMAGE:$TAG" "$UI_IMAGE:latest"
    docker push "$UI_IMAGE:latest"
    log_success "Pushed latest tags"
fi

log_info ""
log_success "=========================================="
log_success "Docker build complete!"
log_success "=========================================="
log_info ""
log_info "Images built:"
log_info "  - $BACKEND_IMAGE:$TAG"
log_info "  - $UI_IMAGE:$TAG"

if [ "$ACTION" = "push" ]; then
    log_info ""
    log_info "To use these images:"
    log_info "  1. Copy docker/docker-compose.user.yml to your machine"
    log_info "  2. Create ~/.antikythera/.env with your credentials"
    log_info "  3. Run: docker-compose -f docker-compose.user.yml up"
fi
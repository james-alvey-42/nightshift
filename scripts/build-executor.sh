#!/bin/bash
# Build the Claude Code executor Docker image

set -e  # Exit on error

# Default values
USER_ID=$(id -u)
GROUP_ID=$(id -g)
IMAGE_NAME="nightshift-claude-executor:latest"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --uid)
            USER_ID="$2"
            shift 2
            ;;
        --gid)
            GROUP_ID="$2"
            shift 2
            ;;
        --image)
            IMAGE_NAME="$2"
            shift 2
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --uid UID       User ID for container user (default: current user)"
            echo "  --gid GID       Group ID for container user (default: current group)"
            echo "  --image NAME    Image name and tag (default: nightshift-claude-executor:latest)"
            echo "  --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

echo "Building Claude Code executor container..."
echo "  User ID: $USER_ID"
echo "  Group ID: $GROUP_ID"
echo "  Image: $IMAGE_NAME"
echo ""

# Build the Docker image
docker build \
    --build-arg USER_ID="$USER_ID" \
    --build-arg GROUP_ID="$GROUP_ID" \
    -t "$IMAGE_NAME" \
    -f docker/claude-executor/Dockerfile \
    .

echo ""
echo "✓ Build complete!"
echo ""
echo "Image: $IMAGE_NAME"
echo ""
echo "To enable containerized execution:"
echo "  export NIGHTSHIFT_USE_DOCKER=true"
echo ""
echo "To test the image:"
echo "  docker run --rm $IMAGE_NAME --version"

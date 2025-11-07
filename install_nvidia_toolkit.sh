#!/bin/bash
# Install NVIDIA Container Toolkit for Docker GPU support

set -e  # Exit on error

echo "Installing NVIDIA Container Toolkit..."

# Detect distribution
. /etc/os-release

# Map Linux Mint to Ubuntu base version
if [ "$ID" = "linuxmint" ]; then
    case "$VERSION_ID" in
        "22.2"|"22")
            distribution="ubuntu24.04"
            echo "Linux Mint $VERSION_ID detected, using Ubuntu 24.04 repository"
            ;;
        "21.2"|"21")
            distribution="ubuntu22.04"
            echo "Linux Mint $VERSION_ID detected, using Ubuntu 22.04 repository"
            ;;
        "20.3"|"20")
            distribution="ubuntu20.04"
            echo "Linux Mint $VERSION_ID detected, using Ubuntu 20.04 repository"
            ;;
        *)
            distribution="ubuntu22.04"
            echo "Linux Mint $VERSION_ID detected, defaulting to Ubuntu 22.04 repository"
            ;;
    esac
else
    distribution="$ID$VERSION_ID"
fi

echo "Using distribution: $distribution"

# Add GPG key
echo "Adding NVIDIA GPG key..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

# Add repository - use generic deb repository for DEB-based distributions
echo "Adding NVIDIA Container Toolkit repository..."
if [ "$ID" = "linuxmint" ] || [ "$ID" = "ubuntu" ] || [ "$ID" = "debian" ]; then
    # Use the generic stable deb repository
    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
      sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
      sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
else
    # Try distribution-specific repository
    curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
      sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
      sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
fi

# Update package list (continue even if some repositories have issues)
echo "Updating package list..."
sudo apt-get update || {
    echo "⚠️  Some repositories had issues, but continuing with NVIDIA installation..."
    # Check if NVIDIA repository is accessible
    if ! apt-cache policy nvidia-container-toolkit > /dev/null 2>&1; then
        echo "❌ ERROR: NVIDIA Container Toolkit repository is not accessible"
        exit 1
    fi
}

# Install NVIDIA Container Toolkit
echo "Installing NVIDIA Container Toolkit..."
sudo apt-get install -y nvidia-container-toolkit

# Configure Docker to use NVIDIA runtime
echo "Configuring Docker runtime..."
sudo nvidia-ctk runtime configure --runtime=docker

# Restart Docker
echo "Restarting Docker..."
sudo systemctl restart docker

echo ""
echo "✅ NVIDIA Container Toolkit installed successfully!"
echo ""
echo "Testing GPU access..."
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi || echo "⚠️  GPU test failed - you may need to restart Docker Desktop or your system"


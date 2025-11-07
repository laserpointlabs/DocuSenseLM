# GPU Setup Instructions for Docker

## Current Situation

You have both Docker Desktop and native Docker Engine installed. For GPU access to work properly, you need to use **native Docker Engine** because Docker Desktop runs in a VM that cannot access the host's nvidia-container-runtime.

## Solution: Switch to Native Docker Engine

### Step 1: Add your user to the docker group

```bash
sudo usermod -aG docker $USER
```

### Step 2: Log out and log back in (or restart)

This is required for the group membership to take effect. Alternatively, you can use:
```bash
newgrp docker
```

### Step 3: Switch Docker context to native Docker Engine

```bash
docker context use default
```

### Step 4: Verify native Docker can see NVIDIA runtime

```bash
docker info | grep -i runtime
```

You should see `nvidia` in the list of runtimes.

### Step 5: Test GPU access

```bash
docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
```

### Step 6: Test with Docker Compose

```bash
cd /home/jdehart/Working/ndaTool
docker compose up -d ollama
docker compose exec ollama nvidia-smi
```

## Why Docker Desktop Doesn't Work

Docker Desktop runs in its own VM/container environment. The nvidia-container-runtime binary exists on your host at `/usr/bin/nvidia-container-runtime`, but Docker Desktop's VM cannot access it. Native Docker Engine runs directly on the host and can access all host binaries and devices.

## Verifying Configuration

After switching to native Docker Engine, verify:

1. **Docker context:**
   ```bash
   docker context show
   # Should show: default
   ```

2. **NVIDIA runtime available:**
   ```bash
   docker info | grep nvidia
   # Should show: nvidia in the runtimes list
   ```

3. **GPU access:**
   ```bash
   docker run --rm --gpus all nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
   # Should show your 4 RTX 4060 Ti GPUs
   ```

## Switching Back to Docker Desktop (if needed)

If you need to use Docker Desktop for other purposes:

```bash
docker context use desktop-linux
```

But note: GPU access will not work with Docker Desktop.




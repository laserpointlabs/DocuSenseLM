# WSL2 GPU Not Working - Fix Steps

## Problem
Ollama shows "100% CPU" instead of GPU, and Windows Task Manager shows no NVIDIA GPU activity.

## Root Cause
WSL2 GPU passthrough can break after:
- Windows updates
- Docker Desktop updates
- WSL2 updates
- NVIDIA driver updates

## Solution Steps (Try in Order)

### Step 1: Restart Docker Desktop (Most Common Fix)
1. **Quit Docker Desktop completely** (not just minimize)
   - Right-click Docker icon in system tray
   - Click "Quit Docker Desktop"
   - Wait 10 seconds

2. **Restart Docker Desktop**
   - Launch Docker Desktop
   - Wait for it to fully start (whale icon stops animating)

3. **Restart Ollama container**
   ```bash
   docker compose restart ollama
   sleep 10
   docker compose exec ollama ollama ps
   # Should now show "100% GPU"
   ```

### Step 2: Verify NVIDIA Driver (Windows)
1. Open **Device Manager** in Windows
2. Check **Display adapters** → Should see your NVIDIA GPU
3. Right-click → **Properties** → Check driver version
4. If outdated or missing, download from: https://www.nvidia.com/Download/index.aspx
   - **IMPORTANT**: Download the **WSL2-compatible** driver (usually latest)

### Step 3: Update WSL2 (Windows)
```powershell
# In Windows PowerShell (as Administrator)
wsl --update
wsl --shutdown
# Wait 10 seconds, then restart WSL
```

### Step 4: Verify GPU Access in WSL2
```bash
# In WSL2
nvidia-smi
# Should show your GPU
```

### Step 5: Force Ollama to Reload Model
```bash
# Unload current model
docker compose exec ollama ollama ps
# Note the model name

# Pull fresh copy (forces GPU detection)
docker compose exec ollama ollama pull llama3.2:3b

# Run a test
docker compose exec ollama ollama run llama3.2:3b "test"

# Check GPU usage
docker compose exec ollama ollama ps
# Should show "100% GPU"
```

### Step 6: Check Docker Runtime Configuration
Your Docker daemon config shows:
```json
{
  "runtimes": {
    "nvidia": {
      "path": "nvidia-container-runtime"
    }
  }
}
```

Verify it's working:
```bash
docker run --rm --runtime=nvidia nvidia/cuda:12.0.0-base-ubuntu22.04 nvidia-smi
# Should show GPU info
```

### Step 7: Nuclear Option - Rebuild Everything
```bash
# Stop all containers
docker compose down

# Remove Ollama container and volume
docker compose rm -f ollama
docker volume rm ndatool_ollama_data  # Optional - deletes downloaded models

# Restart Docker Desktop (see Step 1)

# Start fresh
docker compose up -d ollama
sleep 15

# Pull model fresh
docker compose exec ollama ollama pull llama3.2:3b

# Test
docker compose exec ollama ollama run llama3.2:3b "test"
docker compose exec ollama ollama ps
```

## Verification

After each step, verify GPU is working:

```bash
# 1. Check Ollama is using GPU
docker compose exec ollama ollama ps
# Should show: "100% GPU" (not "100% CPU")

# 2. Check Windows Task Manager
# - Open Task Manager → Performance → GPU
# - Run a model inference
# - Should see GPU activity spike

# 3. Check GPU utilization
nvidia-smi
# Should show GPU utilization > 0% when model is running
```

## Expected Results

**When GPU is working:**
- `ollama ps` shows: `100% GPU`
- Windows Task Manager shows GPU activity
- `nvidia-smi` shows GPU utilization > 0%
- Response times: 5-15 seconds (not 30-60+)

**When GPU is NOT working:**
- `ollama ps` shows: `100% CPU`
- Windows Task Manager shows no GPU activity
- `nvidia-smi` shows 0% utilization
- Response times: 30-60+ seconds (very slow)

## Notes

- **Docker Desktop restart fixes it 90% of the time** in WSL2
- GPU passthrough in WSL2 is fragile - can break after updates
- Sometimes requires Windows restart if Docker restart doesn't work
- The `ollama ps` output is the most reliable indicator - if it says "CPU", GPU isn't being used


# Virtual Environment Usage Guide

## Current Configuration ✅

The Antikythera project is already configured to use the **local virtual environment** (`venv/`) instead of the global Python installation.

### Startup Script Configuration

**File:** `start_antikythera.sh`

```bash
# Line 4-5: Define venv paths
ROOT_DIR="$(pwd)"
VENV_PATH="$ROOT_DIR/venv"
PYTHON_EXE="$VENV_PATH/bin/python3"

# Line 39: Uses venv Python to start backend
PYTHONPATH=$ROOT_DIR $PYTHON_EXE -m uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

### Virtual Environment Status

✅ **Virtual Environment exists:** `venv/`

✅ **Dependencies installed in venv:**
- uvicorn
- fastapi
- python-multipart
- filelock
- httpx
- pydantic-settings
- All other project dependencies

### How to Verify

```bash
# Check which Python is being used
cd /Users/himanshusao/Work/src/extra/himanshu-sao/antikythera
./venv/bin/python --version
# Should show: Python 3.11.x

# Verify dependencies are in venv
./venv/bin/python -c "import uvicorn; print(uvicorn.__file__)"
# Should show path inside ./venv/lib/python3.11/site-packages
```

### Important Notes

1. **Always use the startup scripts** (`./start_antikythera.sh`) to ensure the venv is used
2. **Do NOT use global `python3` or `pip3`** - always use `./venv/bin/python` or `./venv/bin/pip`
3. **When installing new dependencies:**
   ```bash
   ./venv/bin/pip install <package-name>
   ```
4. **When running Python directly:**
   ```bash
   ./venv/bin/python <script.py>
   ```

### Manual Activation (for interactive sessions)

```bash
cd /Users/himanshusao/Work/src/extra/himanshu-sao/antikythera
source venv/bin/activate
python --version  # Should confirm venv is active
```

### Troubleshooting

**Problem:** Dependencies missing or import errors
**Solution:**
```bash
cd /Users/himanshusao/Work/src/extra/himanshu-sao/antikythera
./venv/bin/pip install -r requirements.txt  # If requirements.txt exists
# OR install specific packages:
./venv/bin/pip install uvicorn fastapi python-multipart
```

**Problem:** Processes running with global Python
**Solution:**
```bash
./stop_antikythera.sh  # This kills all processes
./start_antikythera.sh  # This starts with venv Python
```

### Files Modified

- ✅ `start_antikythera.sh` - Already configured correctly
- ✅ `stop_antikythera.sh` - Already configured correctly
- 📄 `activate-venv.sh` - Helper script created (optional)

### Best Practices

1. **Always use the provided startup scripts** instead of manually running uvicorn
2. **Install dependencies only into the venv** using `./venv/bin/pip`
3. **Never use global `pip3` or `python3`** commands in the project directory
4. **Add virtual environment to `.gitignore`** (already done)

---

**Last Updated:** June 02, 2026  
**Status:** ✅ Virtual environment is correctly configured and in use
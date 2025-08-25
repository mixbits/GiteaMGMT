#!/usr/bin/env bash
set -euo pipefail

# Change to script directory
DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$DIR"

# Create logs directory if it doesn't exist
mkdir -p logs

# Create venv if missing
if [[ ! -x "venv/bin/python" ]]; then
  echo "Creating virtual environment..."
  python3 -m venv venv
fi

echo "Upgrading pip and installing dependencies..."
"./venv/bin/python" -m pip install --upgrade pip >/dev/null
"./venv/bin/python" -m pip install -r requirements.txt >/dev/null

echo "Testing tkinter installation..."
"./venv/bin/python" -c "import tkinter; print('Tkinter import test passed')" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ TKINTER IMPORT ERROR DETECTED!"
    echo "Your Python installation is missing tkinter support."
    echo "This is why the GUI won't open."
    echo ""
    echo "SOLUTION: Your virtual environment was created with a Python"
    echo "installation that doesn't have proper tkinter support."
    echo ""
    echo "Fixing automatically..."
    echo ""
    
    # Test system Python first
    python3 -c "import tkinter; print('System Python tkinter: OK')" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "❌ System Python also has tkinter issues!"
        echo "Please install tkinter: sudo apt-get install python3-tk (Ubuntu/Debian)"
        echo "Or: sudo dnf install tkinter (Fedora/RHEL)"
        echo "Or: brew install python-tk (macOS with Homebrew)"
        echo "Or reinstall Python with tkinter support."
        read -p "Press Enter to continue..."
        exit 1
    fi
    
    echo "✅ System Python has working tkinter support."
    echo "Recreating virtual environment with working Python..."
    
    # Remove old venv
    if [ -d "venv" ]; then
        rm -rf "venv"
        echo "✅ Old virtual environment removed."
    fi
    
    # Create new venv
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment!"
        read -p "Press Enter to continue..."
        exit 1
    fi
    
    echo "✅ New virtual environment created."
    echo "Installing dependencies..."
    "./venv/bin/python" -m pip install --upgrade pip >/dev/null
    "./venv/bin/python" -m pip install -r requirements.txt >/dev/null
    echo "✅ Dependencies installed."
    echo ""
fi

# Test tkinter GUI creation (more thorough test)
echo "Testing tkinter GUI creation..."
"./venv/bin/python" -c "import tkinter; root = tkinter.Tk(); root.destroy(); print('Tkinter GUI test passed')" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo ""
    echo "❌ TKINTER GUI CREATION ERROR!"
    echo "Tkinter imports but cannot create GUI windows."
    echo "This may be due to missing display or X11 forwarding."
    echo ""
    echo "SOLUTION: Checking display environment..."
    
    if [ -z "${DISPLAY:-}" ]; then
        echo "❌ No DISPLAY environment variable set."
        echo "If you're using SSH, try: ssh -X username@hostname"
        echo "Or run this on a machine with a graphical desktop."
        read -p "Press Enter to continue..."
        exit 1
    fi
    
    echo "✅ DISPLAY is set to: $DISPLAY"
    echo "GUI creation test failed, but proceeding anyway..."
    echo ""
fi

echo "✅ Tkinter test passed - launching GUI..."
echo ""
echo "Launching Gitea Management Application..."
echo "The GUI window should appear shortly."
echo "Launching in headless mode - this terminal will close automatically."
echo ""

# Launch GUI in background (headless terminal)
nohup "./venv/bin/python" app.py "$@" >/dev/null 2>&1 &
echo "GUI launched successfully. You can close this terminal."
sleep 2  # Give GUI time to start
exit 0
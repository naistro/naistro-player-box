#!/bin/bash

echo "Setting up the project..."

# Create a virtual environment if not exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
else
    echo "Virtual environment already exists."
fi

# Activate the virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Install mpv based on the operating system
echo "Installing mpv library..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if ! command -v mpv &> /dev/null; then
        echo "Installing mpv on macOS..."
        brew install mpv
    else
        echo "mpv is already installed on macOS."
    fi

    # Ensure libmpv.dylib is linked correctly
    LIBMPV_PATH=$(find /opt/homebrew/Cellar/mpv -name "libmpv.dylib" | head -n 1)
    if [ -n "$LIBMPV_PATH" ]; then
        echo "Found libmpv.dylib at $LIBMPV_PATH"
        if [ ! -e "/usr/local/lib/libmpv.dylib" ]; then
            echo "Creating symbolic link for libmpv.dylib..."
            sudo ln -s "$LIBMPV_PATH" /usr/local/lib/libmpv.dylib
        else
            echo "Symbolic link for libmpv.dylib already exists."
        fi
    else
        echo "libmpv.dylib not found, please ensure mpv is installed correctly."
    fi

elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    if ! command -v mpv &> /dev/null; then
        echo "Installing mpv on Linux..."
        sudo apt-get update && sudo apt-get install -y mpv
    else
        echo "mpv is already installed on Linux."
    fi
elif [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    # Windows (using MSYS2 or Cygwin)
    if ! command -v mpv &> /dev/null; then
        echo "Please install mpv manually on Windows."
        echo "Visit https://mpv.io/installation/ for instructions."
    else
        echo "mpv is already installed on Windows."
    fi
else
    echo "Unsupported OS: $OSTYPE"
    echo "Please install mpv manually. Visit https://mpv.io/installation/ for instructions."
fi
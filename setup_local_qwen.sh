#!/bin/bash

# setup.sh: Configure Qwen3-0.6B locally with Ollama, with minimal output, yes/no test, and enhanced CLI/API prompts

# Exit on error
set -e

# Variables
OLLAMA_VERSION="latest"
MODEL_NAME="qwen3:0.6b"
OLLAMA_URL="https://ollama.com/install.sh"
INSTALL_DIR="$HOME/ollama_qwen"
CONFIG_FILE="$INSTALL_DIR/Modelfile"
GITHUB_API_URL="https://api.github.com/repos/ollama/ollama/releases/latest"
OLLAMA_PORT="11434"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to print messages
log() {
    echo -e "${GREEN}[INFO] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

# Check for curl
if ! command -v curl &> /dev/null; then
    error "curl is required. Please install it (e.g., sudo apt install curl on Ubuntu)."
fi

# Check for netstat or lsof
if ! command -v netstat &> /dev/null && ! command -v lsof &> /dev/null; then
    error "netstat or lsof is required to check port usage. Install net-tools or lsof (e.g., sudo apt install net-tools lsof)."
fi

# Check for ps
if ! command -v ps &> /dev/null; then
    error "ps is required to check process names. Install procps (e.g., sudo apt install procps)."
fi

# Check for bash
if [ ! "$BASH_VERSION" ]; then
    error "This script must be run with bash."
fi

# Check if Ollama service is running
check_ollama_service() {
    if command -v systemctl &> /dev/null && systemctl is-active --quiet ollama; then
        log "Ollama service is running via systemd."
        return 0
    fi

    local PID=""
    if command -v lsof &> /dev/null; then
        PID=$(lsof -i :$OLLAMA_PORT -t 2>/dev/null)
    elif command -v netstat &> /dev/null; then
        PID=$(netstat -tulnp 2>/dev/null | grep ":$OLLAMA_PORT" | awk '{print $7}' | cut -d'/' -f1)
    fi

    if [ -n "$PID" ]; then
        local PROCESS_NAME=$(ps -p "$PID" -o comm= 2>/dev/null)
        if [[ "$PROCESS_NAME" == *"ollama"* ]]; then
            log "Ollama is running on port $OLLAMA_PORT."
            return 0
        fi
    fi
    return 1
}

# Check if Ollama is installed and up-to-date
check_ollama() {
    if command -v ollama &> /dev/null; then
        log "Ollama is installed."
        INSTALLED_VERSION=$(ollama version 2>/dev/null | grep -oP 'version \K[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
        LATEST_VERSION=$(curl -s "$GITHUB_API_URL" | grep '"tag_name":' | grep -oP 'v\K[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
        if [ "$INSTALLED_VERSION" != "unknown" ] && [ "$LATEST_VERSION" != "unknown" ] && [ "$INSTALLED_VERSION" = "$LATEST_VERSION" ]; then
            log "Ollama is up-to-date (version $INSTALLED_VERSION)."
            return 0
        elif check_ollama_service; then
            log "Ollama is running, skipping update."
            return 0
        else
            log "Ollama is outdated. Updating..."
            return 1
        fi
    else
        log "Ollama not found. Installing..."
        return 1
    fi
}

# Check if port is in use and identify the process
check_port() {
    local PID=""
    if command -v lsof &> /dev/null; then
        PID=$(lsof -i :$OLLAMA_PORT -t 2>/dev/null)
    elif command -v netstat &> /dev/null; then
        PID=$(netstat -tulnp 2>/dev/null | grep ":$OLLAMA_PORT" | awk '{print $7}' | cut -d'/' -f1)
    fi

    if [ -z "$PID" ]; then
        return 0
    fi

    local PROCESS_NAME=$(ps -p "$PID" -o comm= 2>/dev/null)
    if [ -z "$PROCESS_NAME" ]; then
        return 1
    fi

    if [[ "$PROCESS_NAME" == *"ollama"* ]]; then
        return 1
    else
        return 2
    fi
}

# Resolve port conflict
resolve_port_conflict() {
    local STATUS=$1
    local PID=""
    if command -v lsof &> /dev/null; then
        PID=$(lsof -i :$OLLAMA_PORT -t 2>/dev/null)
    elif command -v netstat &> /dev/null; then
        PID=$(netstat -tulnp 2>/dev/null | grep ":$OLLAMA_PORT" | awk '{print $7}' | cut -d'/' -f1)
    fi

    if [ "$STATUS" -eq 1 ]; then
        log "Terminating Ollama process (PID $PID)..."
        kill -9 "$PID"
        sleep 2
        if lsof -i :$OLLAMA_PORT &> /dev/null; then
            error "Failed to free port $OLLAMA_PORT."
        fi
    elif [ "$STATUS" -eq 2 ]; then
        error "Port $OLLAMA_PORT is used by a non-Ollama process (PID $PID). Stop it or set OLLAMA_HOST (e.g., export OLLAMA_HOST='127.0.0.1:11435')."
    fi
}

# Install or update Ollama
install_ollama() {
    log "Installing/updating Ollama..."
    if ! curl -fsSL "$OLLAMA_URL" | sh; then
        error "Failed to install/update Ollama."
    fi
}

# Check if qwen3-custom model exists and create if missing
check_custom_model() {
    if ollama list 2>/dev/null | grep -q "qwen3-custom"; then
        log "qwen3-custom model exists."
        return 0
    else
        log "Creating qwen3-custom model..."
        if [ ! -f "$CONFIG_FILE" ]; then
            log "Creating Modelfile at $CONFIG_FILE..."
            mkdir -p "$INSTALL_DIR"
            cat << EOF > "$CONFIG_FILE"
FROM $MODEL_NAME
PARAMETER temperature 0.6
PARAMETER top_p 0.95
PARAMETER top_k 20
PARAMETER num_ctx 4096
SYSTEM "You are Qwen3, a helpful AI assistant created by Alibaba Cloud."
EOF
        fi
        if ! ollama create qwen3-custom -f "$CONFIG_FILE" >/dev/null 2>&1; then
            error "Failed to create qwen3-custom model. Check $CONFIG_FILE and $MODEL_NAME."
        fi
        log "qwen3-custom model created."
        return 0
    fi
}

# Create installation directory
mkdir -p "$INSTALL_DIR" || error "Failed to create directory $INSTALL_DIR"

# Check if Ollama is installed and running
if check_ollama; then
    log "Ollama is ready. Skipping installation."
else
    install_ollama
fi

# Verify Ollama installation
if ! command -v ollama &> /dev/null; then
    error "Ollama installation failed."
fi

# Set minimal logging for Ollama
export OLLAMA_DEBUG=false

# Skip starting service if already running
if check_ollama_service; then
    OLLAMA_PID=$(lsof -i :$OLLAMA_PORT -t 2>/dev/null || echo "unknown")
else
    check_port
    PORT_STATUS=$?
    if [ "$PORT_STATUS" -ne 0 ]; then
        resolve_port_conflict "$PORT_STATUS"
    fi

    log "Starting Ollama service..."
    ollama serve >/dev/null 2>&1 &
    OLLAMA_PID=$!
    sleep 3
    if ! ps -p $OLLAMA_PID > /dev/null; then
        error "Ollama service failed to start."
    fi
fi

# Pull Qwen3-0.6B model
log "Downloading Qwen3-0.6B model..."
if ! ollama pull "$MODEL_NAME" >/dev/null 2>&1; then
    error "Failed to pull $MODEL_NAME."
fi

# Check and create qwen3-custom model
check_custom_model

# Test the model with a yes/no question
log "Testing model with 'Is the sky blue?'..."
if ! echo "Is the sky blue? /think" | ollama run qwen3-custom >/dev/null 2>&1; then
    error "Model test failed. Check Ollama service and model."
fi
log "Model test passed."

# Save the example Python script
cat << EOF > "$INSTALL_DIR/test_qwen3.py"
import requests
url = "http://localhost:11434/api/chat"
data = {
    "model": "qwen3-custom",
    "messages": [{"role": "user", "content": "Hello, Qwen3! Tell me a joke. /think"}],
    "stream": False
}
response = requests.post(url, json=data)
print(response.json()['message']['content'])
EOF

# Prompt user for how to run Qwen3
log "Setup complete!"
echo -e "${GREEN}Run Qwen3 now?${NC}"
echo "1) CLI: 'ollama run qwen3-custom'"
echo "2) API: 'python3 $INSTALL_DIR/test_qwen3.py' (needs 'requests')"
echo -n "Enter 1, 2, or press Enter to skip: "
read choice

case $choice in
    1)
        clear
        echo -e "${GREEN}Ready${NC}"
        echo "Type your question, e.g., 'Is the sky blue?'"
        ollama run qwen3-custom
        ;;
    2)
        clear
        echo -e "${GREEN}Qwen3 API Ready${NC}"
        echo "Example API call:"
        echo 'curl -X POST http://localhost:11434/api/chat -d "{\"model\":\"qwen3-custom\",\"messages\":[{\"role\":\"user\",\"content\":\"Is the sun hot? /think\"}],\"stream\":false}"'
        log "Checking Python 'requests'..."
        if ! python3 -c "import requests" 2>/dev/null; then
            log "Installing 'requests'..."
            if ! pip3 install requests >/dev/null 2>&1; then
                error "Failed to install 'requests'. Run 'pip3 install requests' manually."
            fi
        fi
        log "Running Qwen3 API script..."
        python3 "$INSTALL_DIR/test_qwen3.py"
        ;;
    *)
        log "You can run Qwen3 later with:"
        echo -e "${GREEN}CLI:${NC} ollama run qwen3-custom"
        echo -e "${GREEN}API:${NC} python3 $INSTALL_DIR/test_qwen3.py"
        ;;
esac

log "To stop Ollama: kill $OLLAMA_PID"
exit 0

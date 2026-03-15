#!/bin/bash
# =============================================================================
# PiHome Bootstrap Script
# This is the script hosted at https://pihome.io/install
# Usage: curl -sSL https://pihome.io/install | bash
#   or:  curl -sSL https://pihome.io/install | bash -s -- --skip-airplay
# =============================================================================
set -uo pipefail

readonly PIHOME_DIR="/usr/local/PiHome"
readonly PIHOME_REPO="https://github.com/bradleyasu/PiHomeV2.git"

# Colors (fallback gracefully)
if command -v tput &>/dev/null && tput colors &>/dev/null; then
    PINK=$(tput setaf 200 2>/dev/null || echo "")
    RED=$(tput setaf 1 2>/dev/null || echo "")
    GREEN=$(tput setaf 2 2>/dev/null || echo "")
    DIM=$(tput dim 2>/dev/null || echo "")
    BOLD=$(tput bold 2>/dev/null || echo "")
    RESET=$(tput sgr0 2>/dev/null || echo "")
else
    PINK="" RED="" GREEN="" DIM="" BOLD="" RESET=""
fi

echo ""
echo "${PINK}"
echo '  ______ _ _   _                      '
echo '  | ___ (_) | | |                     '
echo '  | |_/ /_| |_| | ___  _ __ ___   ___ '
echo '  |  __/| |  _  |/ _ \| '"'"'_ ` _ \ / _ \'
echo '  | |   | | | | | (_) | | | | | |  __/'
echo '  \_|   |_\_| |_/\___/|_| |_| |_|\___|'
echo "${RESET}"
echo "  ${DIM}https://pihome.io${RESET}"
echo ""

# --- Pre-checks ---

# Internet check (use wget as fallback since curl may not be installed yet)
if command -v curl &>/dev/null; then
    if ! curl -s --max-time 5 https://github.com >/dev/null 2>&1; then
        echo "  ${RED}[ERR]${RESET} No internet connectivity"
        exit 1
    fi
elif command -v wget &>/dev/null; then
    if ! wget -q --timeout=5 --spider https://github.com 2>/dev/null; then
        echo "  ${RED}[ERR]${RESET} No internet connectivity"
        exit 1
    fi
else
    # No curl or wget — we'll install them, but can't check internet first
    echo "  ${DIM}[--]${RESET} Cannot verify internet (curl/wget not found, will attempt install)"
fi
echo "  ${GREEN}[ok]${RESET} Internet connectivity"

# Install bootstrap dependencies
echo ""
echo "  ${BOLD}Installing prerequisites...${RESET}"
if ! sudo apt-get -y update >/dev/null 2>&1; then
    echo "  ${RED}[ERR]${RESET} apt-get update failed. Are you connected to the internet?"
    exit 1
fi
if ! sudo apt-get -y install git vim curl >/dev/null 2>&1; then
    echo "  ${RED}[ERR]${RESET} Failed to install prerequisites (git, vim, curl)"
    exit 1
fi
echo "  ${GREEN}[ok]${RESET} Prerequisites installed (git, vim, curl)"

# --- Fetch PiHome ---

echo ""
if [ -d "$PIHOME_DIR/.git" ]; then
    echo "  ${BOLD}Updating PiHome...${RESET}"
    if ! git -C "$PIHOME_DIR" pull --ff-only 2>/dev/null; then
        echo "  ${RED}[ERR]${RESET} Failed to update repository"
        echo "  ${DIM}  You may need to resolve conflicts in ${PIHOME_DIR}${RESET}"
        exit 1
    fi
    echo "  ${GREEN}[ok]${RESET} Repository updated"
else
    echo "  ${BOLD}Downloading PiHome...${RESET}"
    if ! sudo git clone "$PIHOME_REPO" "$PIHOME_DIR" 2>/dev/null; then
        echo "  ${RED}[ERR]${RESET} Failed to clone repository"
        exit 1
    fi
    echo "  ${GREEN}[ok]${RESET} Repository cloned to ${PIHOME_DIR}"
fi

# --- Hand off to installer ---

chmod 755 "$PIHOME_DIR/setup/"*.sh

echo ""
echo "  ${DIM}Launching installer...${RESET}"
echo ""

exec sudo bash "$PIHOME_DIR/setup/install.sh" --unattended "$@"

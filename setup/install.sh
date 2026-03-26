#!/bin/bash
# =============================================================================
# PiHome Installer
# Install: sudo curl -sSL https://pihome.io/install | bash
# =============================================================================
set -uo pipefail

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
readonly PIHOME_VERSION="1.0.0"
readonly PIHOME_DIR="/usr/local/PiHome"
readonly PIHOME_REPO="https://github.com/bradleyasu/PiHomeV2.git"
readonly SDL2_CDN="https://cdn.pihome.io/bin"
readonly LOG_FILE="/tmp/pihome-install.log"
readonly STATE_FILE="/tmp/pihome-install-state"
readonly REQUIRED_DISK_MB=2048
readonly TOTAL_PHASES=9

# Options (overridden by CLI flags)
SKIP_AIRPLAY=false
VERBOSE=false
UNATTENDED=false

# Track warnings for summary
WARNINGS=()

# -----------------------------------------------------------------------------
# UX Utilities
# -----------------------------------------------------------------------------

# Colors (fallback gracefully if tput unavailable)
if command -v tput &>/dev/null && tput colors &>/dev/null; then
    PINK=$(tput setaf 200 2>/dev/null || echo "")
    GREEN=$(tput setaf 2 2>/dev/null || echo "")
    YELLOW=$(tput setaf 3 2>/dev/null || echo "")
    RED=$(tput setaf 1 2>/dev/null || echo "")
    BOLD=$(tput bold 2>/dev/null || echo "")
    DIM=$(tput dim 2>/dev/null || echo "")
    RESET=$(tput sgr0 2>/dev/null || echo "")
else
    PINK="" GREEN="" YELLOW="" RED="" BOLD="" DIM="" RESET=""
fi

print_banner() {
    echo ""
    echo "${PINK}"
    echo '  ______ _ _   _                      '
    echo '  | ___ (_) | | |                     '
    echo '  | |_/ /_| |_| | ___  _ __ ___   ___ '
    echo '  |  __/| |  _  |/ _ \| '"'"'_ ` _ \ / _ \'
    echo '  | |   | | | | | (_) | | | | | |  __/'
    echo '  \_|   |_\_| |_/\___/|_| |_| |_|\___|'
    echo "${RESET}"
    echo "  ${DIM}Installer v${PIHOME_VERSION}${RESET}"
    echo "  ======================================"
    echo ""
}

print_header() {
    local num="$1" total="$2" desc="$3"
    echo ""
    echo "  ${BOLD}[${num}/${total}] ${desc}${RESET}"
    echo "  $(printf '%.0s-' {1..40})"
}

print_step() {
    printf "  ${DIM}->  %s${RESET}" "$1"
}

print_step_done() {
    printf "\r  ${GREEN}[ok]${RESET} %s\n" "$1"
}

print_success() {
    echo "  ${GREEN}[ok]${RESET} $1"
}

print_warning() {
    echo "  ${YELLOW}[!!]${RESET} $1"
    WARNINGS+=("$1")
}

print_error() {
    echo "  ${RED}[ERR]${RESET} $1"
}

print_check_pass() {
    echo "  ${GREEN}[ok]${RESET} $1"
}

print_check_warn() {
    echo "  ${YELLOW}[!!]${RESET} $1"
}

print_check_fail() {
    echo "  ${RED}[FAIL]${RESET} $1"
}

# Spinner: runs while a background PID is alive
# Usage: spin $pid "Doing something"
spin() {
    local pid="$1" message="$2"
    local chars='|/-\'
    local i=0 elapsed=0
    while kill -0 "$pid" 2>/dev/null; do
        printf "\r  ${DIM} %s  %s (%ds)${RESET}   " "${chars:$((i % 4)):1}" "$message" "$elapsed"
        sleep 1
        elapsed=$((elapsed + 1))
        i=$((i + 1))
    done
    printf "\r%80s\r" ""  # clear line
}

# Core wrapper: run a command with spinner and logging
# On failure: offers Retry / Skip / Abort
# Usage: run_logged "Description" command arg1 arg2 ...
run_logged() {
    local description="$1"
    shift

    while true; do
        print_step "$description"

        if [ "$VERBOSE" = true ]; then
            "$@" 2>&1 | tee -a "$LOG_FILE" &
        else
            "$@" >> "$LOG_FILE" 2>&1 &
        fi
        local pid=$!

        if [ "$VERBOSE" = false ]; then
            spin $pid "$description"
        fi

        local exit_code=0
        wait $pid || exit_code=$?

        if [ $exit_code -eq 0 ]; then
            print_step_done "$description"
            return 0
        fi

        print_error "$description failed (exit code $exit_code)"
        echo "  ${DIM}See ${LOG_FILE} for details${RESET}"

        if [ "$UNATTENDED" = true ]; then
            print_error "Aborting (unattended mode)"
            exit 1
        fi

        echo ""
        local choice
        read -rp "  [R]etry / [S]kip / [A]bort? " choice < /dev/tty
        case "$choice" in
            [Rr]*) echo ""; continue ;;
            [Ss]*) print_warning "Skipped: $description"; return 0 ;;
            [Aa]*) echo "  Aborting installation."; exit 1 ;;
            *)     echo "  Aborting installation."; exit 1 ;;
        esac
    done
}

# Prompt user for yes/no (curl-pipe safe)
confirm() {
    local prompt="$1" default="${2:-y}"
    if [ "$UNATTENDED" = true ]; then
        return 0
    fi
    local choice
    read -rp "  $prompt " choice < /dev/tty
    case "$default" in
        y) [[ ! "$choice" =~ ^[Nn] ]] ;;
        n) [[ "$choice" =~ ^[Yy] ]] ;;
    esac
}

# -----------------------------------------------------------------------------
# Pre-flight Checks
# -----------------------------------------------------------------------------
preflight_checks() {
    echo "  ${BOLD}Pre-flight checks${RESET}"
    echo "  $(printf '%.0s-' {1..40})"

    local hard_fail=false

    # OS check
    if [ -f /etc/os-release ]; then
        # shellcheck source=/dev/null
        . /etc/os-release
        if [[ "${ID:-}" == "raspbian" || "${ID_LIKE:-}" == *"debian"* || "${ID:-}" == "debian" ]]; then
            print_check_pass "OS: ${PRETTY_NAME:-$ID}"
        else
            print_check_warn "OS: ${PRETTY_NAME:-$ID} (expected Raspberry Pi OS / Debian)"
        fi
    else
        print_check_warn "Could not detect OS"
    fi

    # Architecture
    local arch
    arch=$(uname -m)
    if [[ "$arch" == "armv7l" || "$arch" == "aarch64" ]]; then
        print_check_pass "Architecture: $arch"
    else
        print_check_warn "Architecture: $arch (expected armv7l or aarch64)"
    fi

    # Disk space
    local avail_mb
    avail_mb=$(df -m /usr/local 2>/dev/null | awk 'NR==2 {print $4}')
    if [ -n "$avail_mb" ] && [ "$avail_mb" -ge "$REQUIRED_DISK_MB" ]; then
        print_check_pass "Disk space: ${avail_mb}MB available"
    elif [ -n "$avail_mb" ]; then
        print_check_fail "Disk space: ${avail_mb}MB available (need ${REQUIRED_DISK_MB}MB)"
        hard_fail=true
    else
        print_check_warn "Could not check disk space"
    fi

    # Internet
    if curl -s --max-time 5 "$SDL2_CDN" >/dev/null 2>&1; then
        print_check_pass "Internet connectivity"
    elif curl -s --max-time 5 https://github.com >/dev/null 2>&1; then
        print_check_warn "CDN unreachable, but internet works"
    else
        print_check_fail "No internet connectivity"
        hard_fail=true
    fi

    # Python 3
    if command -v python3 &>/dev/null; then
        local pyver
        pyver=$(python3 --version 2>&1 | awk '{print $2}')
        local pymajor pyminor
        pymajor=$(echo "$pyver" | cut -d. -f1)
        pyminor=$(echo "$pyver" | cut -d. -f2)
        if [ "$pymajor" -ge 3 ] && [ "$pyminor" -ge 9 ]; then
            print_check_pass "Python $pyver"
        else
            print_check_warn "Python $pyver (3.9+ recommended)"
        fi
    else
        print_check_warn "Python 3 not found (will be installed)"
    fi

    # Existing installation
    if [ -d "$PIHOME_DIR" ]; then
        print_check_warn "Existing installation found at $PIHOME_DIR"
        if ! confirm "Upgrade existing installation? [Y/n]" "y"; then
            echo "  Aborting."
            exit 0
        fi
    fi

    # Resume state
    if [ -f "$STATE_FILE" ]; then
        local completed
        completed=$(wc -l < "$STATE_FILE" | tr -d ' ')
        print_check_warn "Previous install state found ($completed phases completed)"
        echo "  ${DIM}  Completed phases will be skipped. Use --clean to start fresh.${RESET}"
    fi

    echo ""

    if [ "$hard_fail" = true ]; then
        print_error "Pre-flight checks failed. Please fix the issues above and re-run."
        exit 1
    fi
}

# -----------------------------------------------------------------------------
# Resume / State Tracking
# -----------------------------------------------------------------------------
mark_phase_complete() {
    echo "$1" >> "$STATE_FILE"
}

is_phase_complete() {
    [ -f "$STATE_FILE" ] && grep -qx "$1" "$STATE_FILE" 2>/dev/null
}

# -----------------------------------------------------------------------------
# Phase 1: Setup Directories
# -----------------------------------------------------------------------------
phase_setup_directories() {
    local phase_id="setup_directories"
    if is_phase_complete "$phase_id"; then
        print_success "Directories already set up, skipping"
        return 0
    fi

    print_header 1 "$TOTAL_PHASES" "Setting up directories"

    if [ ! -d "$PIHOME_DIR" ]; then
        if sudo mkdir -p "$PIHOME_DIR"; then
            print_success "Created $PIHOME_DIR"
        else
            print_error "Failed to create $PIHOME_DIR"
            exit 1
        fi
    else
        print_success "$PIHOME_DIR exists"
    fi

    # Initialize log
    echo "=== PiHome Install Log - $(date) ===" > "$LOG_FILE"
    print_success "Log file: $LOG_FILE"

    mark_phase_complete "$phase_id"
}

# -----------------------------------------------------------------------------
# Phase 2: Clone Repository
# -----------------------------------------------------------------------------
phase_clone_repository() {
    local phase_id="clone_repository"
    if is_phase_complete "$phase_id"; then
        print_success "Repository already cloned, skipping"
        return 0
    fi

    print_header 2 "$TOTAL_PHASES" "Fetching PiHome"

    if [ -d "$PIHOME_DIR/.git" ]; then
        # Already cloned (likely via bootstrap.sh), just ensure it's current
        print_success "Repository present at $PIHOME_DIR"
    else
        run_logged "Cloning repository" sudo git clone "$PIHOME_REPO" "$PIHOME_DIR"
    fi

    mark_phase_complete "$phase_id"
}

# -----------------------------------------------------------------------------
# Phase 3: System Dependencies
# -----------------------------------------------------------------------------
phase_system_dependencies() {
    local phase_id="system_dependencies"
    if is_phase_complete "$phase_id"; then
        print_success "System dependencies already installed, skipping"
        return 0
    fi

    print_header 3 "$TOTAL_PHASES" "Installing system dependencies"

    run_logged "Updating package lists" \
        sudo apt-get -y update

    run_logged "Installing core packages" \
        sudo apt-get -y install \
            python3-setuptools git-core python3-dev python3-pip

    run_logged "Installing graphics libraries" \
        sudo apt-get -y install \
            pkg-config libgl1-mesa-dev libgles2-mesa-dev \
            mesa-common-dev libfreetype6-dev libdrm-dev libgbm-dev \
            libudev-dev liblzma-dev libjpeg-dev libtiff-dev libwebp-dev \
            libmtdev-dev libmtdev1 xclip xsel

    run_logged "Installing GStreamer" \
        sudo apt-get -y install \
            libgstreamer1.0-dev \
            gstreamer1.0-plugins-bad gstreamer1.0-plugins-base \
            gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly \
            gstreamer1.0-alsa gstreamer1.0-pulseaudio

    run_logged "Installing SDL2 development libraries" \
        sudo apt-get -y install \
            libsdl2-dev libsdl2-image-dev libsdl2-ttf-dev libsdl2-mixer-dev

    run_logged "Installing display/input libraries" \
        sudo apt-get -y install \
            gir1.2-ibus-1.0 libdbus-1-dev libegl1-mesa-dev \
            libibus-1.0-5 libibus-1.0-dev libice-dev libsm-dev libsndio-dev \
            libwayland-bin libwayland-dev libxi-dev libxinerama-dev \
            libxkbcommon-dev libxrandr-dev libxss-dev libxt-dev libxv-dev \
            x11proto-randr-dev x11proto-scrnsaver-dev \
            x11proto-video-dev x11proto-xinerama-dev

    run_logged "Installing media packages" \
        sudo apt-get -y install \
            ffmpeg mplayer mpv libmpv1

    run_logged "Installing audio support" \
        sudo apt-get -y install \
            libportaudio2 python3-cffi libasound2-dev

    run_logged "Installing image processing" \
        sudo apt-get -y install \
            libopenjp2-7

    run_logged "Installing build tools" \
        sudo apt-get -y install \
            build-essential git autoconf automake libtool libopenblas-dev

    mark_phase_complete "$phase_id"
}

# -----------------------------------------------------------------------------
# Phase 4: Build SDL2 from Source
# -----------------------------------------------------------------------------
build_sdl_component() {
    local url="$1" configure_flags="${2:-}"
    local tarball="${url##*/}"
    local dirname="${tarball%.tar.gz}"

    (
        cd /tmp || exit 1
        [ -f "$tarball" ] || wget -q "$url" -O "$tarball"
        tar -zxf "$tarball"
        cd "$dirname" || exit 1
        if [ -n "$configure_flags" ]; then
            # Word splitting is intentional here for multiple flags
            # shellcheck disable=SC2086
            ./configure $configure_flags
        else
            ./configure
        fi
        make -j"$(nproc)"
        sudo make install
    )
    # Clean up
    rm -rf "/tmp/$tarball" "/tmp/$dirname"
}

phase_build_sdl2() {
    local phase_id="build_sdl2"
    if is_phase_complete "$phase_id"; then
        print_success "SDL2 already built, skipping"
        return 0
    fi

    print_header 4 "$TOTAL_PHASES" "Building SDL2 libraries (this takes a while)"

    run_logged "Building SDL2 2.0.10" \
        build_sdl_component \
            "${SDL2_CDN}/SDL2-2.0.10.tar.gz" \
            "--enable-video-kmsdrm --disable-video-opengl --disable-video-x11 --disable-video-rpi"

    run_logged "Building SDL2_image 2.0.5" \
        build_sdl_component \
            "${SDL2_CDN}/SDL2_image-2.0.5.tar.gz"

    run_logged "Building SDL2_mixer 2.0.4" \
        build_sdl_component \
            "${SDL2_CDN}/SDL2_mixer-2.0.4.tar.gz"

    run_logged "Building SDL2_ttf 2.0.15" \
        build_sdl_component \
            "${SDL2_CDN}/SDL2_ttf-2.0.15.tar.gz"

    mark_phase_complete "$phase_id"
}

# -----------------------------------------------------------------------------
# Phase 5: Build AirPlay (shairport-sync)
# -----------------------------------------------------------------------------
phase_build_airplay() {
    local phase_id="build_airplay"
    if is_phase_complete "$phase_id"; then
        print_success "AirPlay already built, skipping"
        return 0
    fi

    if [ "$SKIP_AIRPLAY" = true ]; then
        print_header 5 "$TOTAL_PHASES" "AirPlay support (skipped)"
        print_warning "AirPlay skipped via --skip-airplay"
        mark_phase_complete "$phase_id"
        return 0
    fi

    print_header 5 "$TOTAL_PHASES" "Building AirPlay support"

    # AirPlay-specific dependencies
    run_logged "Installing AirPlay build dependencies" \
        sudo apt-get -y install --no-install-recommends \
            libpopt-dev libconfig-dev libasound2-dev avahi-daemon \
            libavahi-client-dev libssl-dev libsoxr-dev libplist-dev \
            libsodium-dev uuid-dev libgcrypt-dev xxd libplist-utils \
            libavutil-dev libavcodec-dev libavformat-dev

    # systemd-dev is required on Debian 13+ / Ubuntu 24.10+
    run_logged "Installing systemd-dev (if available)" \
        bash -c 'sudo apt-get -y install systemd-dev 2>/dev/null || true'

    # nqptp
    run_logged "Building nqptp" bash -c '
        cd /tmp
        rm -rf nqptp
        git clone https://github.com/bradleyasu/nqptp.git
        cd nqptp
        autoreconf -fi
        ./configure --with-systemd-startup
        make
        sudo make install
        rm -rf /tmp/nqptp
    '

    run_logged "Enabling nqptp service" bash -c '
        sudo systemctl enable nqptp
        sudo systemctl start nqptp
    '

    # shairport-sync
    run_logged "Building shairport-sync" bash -c '
        cd /tmp
        rm -rf shairport-sync
        git clone https://github.com/bradleyasu/shairport-sync.git
        cd shairport-sync
        autoreconf -fi
        ./configure --sysconfdir=/etc --with-alsa --with-soxr --with-avahi \
            --with-ssl=openssl --with-systemd-startup --with-airplay-2 \
            --with-metadata
        make
        sudo make install
        rm -rf /tmp/shairport-sync
    '

    # Configure shairport-sync: name "PiHome", use DAC at hw:1,0 if available
    run_logged "Configuring shairport-sync" bash -c '
        CONF="/etc/shairport-sync.conf"
        if [ -f "$CONF" ]; then
            # Set the AirPlay name to "PiHome"
            sudo sed -i "s|^//.*name = .*|        name = \"PiHome\";|" "$CONF"
            sudo sed -i "s|^[[:space:]]*name = .*|        name = \"PiHome\";|" "$CONF"

            # If hw:1,0 (RPi DAC Pro) is available, configure ALSA output
            if aplay -l 2>/dev/null | grep -q "card 1"; then
                sudo sed -i "s|^//.*output_device = .*|        output_device = \"hw:1,0\";|" "$CONF"
                sudo sed -i "s|^[[:space:]]*output_device = .*|        output_device = \"hw:1,0\";|" "$CONF"
            fi

            # Enable metadata pipe for Now Playing display
            # The default config has a metadata block with all lines commented out (// prefix).
            # Uncomment and set the values we need. If no metadata block exists, append one.
            if grep -q "^metadata" "$CONF"; then
                sudo sed -i "s|^//[[:space:]]*enabled = .*|        enabled = \"yes\";|" "$CONF"
                sudo sed -i "s|^//[[:space:]]*include_cover_art = .*|        include_cover_art = \"yes\";|" "$CONF"
                sudo sed -i "s|^//[[:space:]]*pipe_name = .*|        pipe_name = \"/tmp/shairport-sync-metadata\";|" "$CONF"
                sudo sed -i "s|^//[[:space:]]*pipe_timeout = .*|        pipe_timeout = 5000;|" "$CONF"
            else
                sudo tee -a "$CONF" > /dev/null <<MDEOF

metadata = {
        enabled = "yes";
        include_cover_art = "yes";
        pipe_name = "/tmp/shairport-sync-metadata";
        pipe_timeout = 5000;
};
MDEOF
            fi
        else
            # Config file missing — write a minimal one
            sudo tee "$CONF" > /dev/null <<SPSEOF
general = {
        name = "PiHome";
};

alsa = {
        output_device = "hw:1,0";
};

metadata = {
        enabled = "yes";
        include_cover_art = "yes";
        pipe_name = "/tmp/shairport-sync-metadata";
        pipe_timeout = 5000;
};
SPSEOF
        fi
    '

    run_logged "Enabling shairport-sync service" bash -c '
        sudo systemctl enable shairport-sync
        sudo systemctl restart shairport-sync
    '

    # Add user to audio group
    local current_user
    current_user=$(whoami)
    sudo usermod -aG audio "$current_user"
    print_success "Added $current_user to audio group"

    # Disable WiFi power management to prevent AirPlay audio dropouts
    if command -v iwconfig &>/dev/null && iwconfig wlan0 2>/dev/null | grep -q "Power Management:on"; then
        sudo iwconfig wlan0 power off 2>/dev/null || true
        # Make it persist across reboots via dhcpcd hook
        local hook_file="/etc/dhcpcd.exit-hook"
        if ! grep -q "iwconfig wlan0 power off" "$hook_file" 2>/dev/null; then
            echo 'iwconfig wlan0 power off 2>/dev/null' | sudo tee -a "$hook_file" >/dev/null
        fi
        print_success "Disabled WiFi power management (prevents audio dropouts)"
    fi

    mark_phase_complete "$phase_id"
}

# -----------------------------------------------------------------------------
# Phase 6: Python Dependencies
# -----------------------------------------------------------------------------
phase_python_dependencies() {
    local phase_id="python_dependencies"
    if is_phase_complete "$phase_id"; then
        print_success "Python dependencies already installed, skipping"
        return 0
    fi

    print_header 6 "$TOTAL_PHASES" "Installing Python packages"

    run_logged "Installing Kivy" \
        python3 -m pip install --break-system-packages "kivy[base]"

    run_logged "Installing Python dependencies" \
        python3 -m pip install --break-system-packages \
            -r "$PIHOME_DIR/requirements.txt"

    mark_phase_complete "$phase_id"
}

# -----------------------------------------------------------------------------
# Phase 7: Configure Environment
# -----------------------------------------------------------------------------
phase_configure_environment() {
    local phase_id="configure_environment"
    if is_phase_complete "$phase_id"; then
        print_success "Environment already configured, skipping"
        return 0
    fi

    print_header 7 "$TOTAL_PHASES" "Configuring environment"

    local profile="/home/${SUDO_USER:-$USER}/.bashrc"

    # Add aliases idempotently
    if ! grep -q 'alias pihome=' "$profile" 2>/dev/null; then
        {
            echo ""
            echo "# PiHome aliases"
            echo "alias pihome=\"cd ${PIHOME_DIR} && ./launch.sh\""
            echo "alias pihome-update=\"cd ${PIHOME_DIR} && ./update.sh\""
        } >> "$profile"
        print_success "Added shell aliases to $profile"
    else
        print_success "Shell aliases already present"
    fi

    # Make scripts executable
    chmod 755 "$PIHOME_DIR/launch.sh" 2>/dev/null || true
    chmod 755 "$PIHOME_DIR/update.sh" 2>/dev/null || true
    chmod 755 "$PIHOME_DIR/setup/install-service.sh" 2>/dev/null || true
    print_success "Scripts marked executable"

    mark_phase_complete "$phase_id"
}

# -----------------------------------------------------------------------------
# Phase 8: Boot Splash
# -----------------------------------------------------------------------------
phase_boot_splash() {
    local phase_id="boot_splash"
    if is_phase_complete "$phase_id"; then
        print_success "Boot splash already configured, skipping"
        return 0
    fi

    print_header 8 "$TOTAL_PHASES" "Configuring boot splash"

    # Install fbi (framebuffer imageviewer)
    run_logged "Installing fbi" \
        sudo apt-get -y install fbi

    # Install splash service
    sudo cp "$PIHOME_DIR/setup/pihome-splash.service" /etc/systemd/system/
    sudo systemctl daemon-reload
    sudo systemctl enable pihome-splash.service
    print_success "Splash service installed and enabled"

    # Quiet the boot console (suppress kernel messages, cursor, logo)
    local cmdline="/boot/cmdline.txt"
    if [ ! -f "$cmdline" ] && [ -f "/boot/firmware/cmdline.txt" ]; then
        cmdline="/boot/firmware/cmdline.txt"
    fi

    if [ -f "$cmdline" ]; then
        # Back up original
        sudo cp "$cmdline" "${cmdline}.bak"

        local quiet_opts="quiet splash loglevel=0 logo.nologo vt.global_cursor_default=0 consoleblank=0"
        local current
        current=$(cat "$cmdline")

        # Add each option if not already present
        for opt in $quiet_opts; do
            if ! echo "$current" | grep -q "$opt"; then
                current="$current $opt"
            fi
        done

        echo "$current" | sudo tee "$cmdline" > /dev/null
        print_success "Boot console quieted ($cmdline)"
    else
        print_warning "Could not find cmdline.txt — boot text will still be visible"
    fi

    # Disable the Raspberry Pi rainbow splash
    local config="/boot/config.txt"
    if [ ! -f "$config" ] && [ -f "/boot/firmware/config.txt" ]; then
        config="/boot/firmware/config.txt"
    fi

    if [ -f "$config" ]; then
        if ! grep -q "disable_splash=1" "$config"; then
            echo "disable_splash=1" | sudo tee -a "$config" > /dev/null
        fi
        print_success "Disabled Raspberry Pi rainbow splash"
    fi

    mark_phase_complete "$phase_id"
}

# -----------------------------------------------------------------------------
# Phase 9: Install Systemd Service
# -----------------------------------------------------------------------------
phase_install_service() {
    local phase_id="install_service"
    if is_phase_complete "$phase_id"; then
        print_success "Service already installed, skipping"
        return 0
    fi

    print_header 9 "$TOTAL_PHASES" "Installing PiHome service"

    sudo cp "$PIHOME_DIR/setup/pihome.service" /etc/systemd/system/
    print_success "Service file installed"

    sudo systemctl daemon-reload
    print_success "Systemd reloaded"

    sudo systemctl enable pihome.service
    print_success "PiHome service enabled (starts on boot)"

    mark_phase_complete "$phase_id"
}

# -----------------------------------------------------------------------------
# Summary
# -----------------------------------------------------------------------------
print_summary() {
    echo ""
    echo "  ${GREEN}${BOLD}========================================${RESET}"
    echo "  ${GREEN}${BOLD}  Installation Complete!${RESET}"
    echo "  ${GREEN}${BOLD}========================================${RESET}"
    echo ""
    echo "  ${BOLD}Installed components:${RESET}"
    is_phase_complete "system_dependencies" && print_success "System dependencies"
    is_phase_complete "build_sdl2"          && print_success "SDL2 libraries"
    is_phase_complete "build_airplay"       && print_success "AirPlay (shairport-sync)"
    is_phase_complete "python_dependencies" && print_success "Python packages"
    is_phase_complete "boot_splash"         && print_success "Boot splash screen"
    is_phase_complete "install_service"     && print_success "PiHome systemd service"

    if [ ${#WARNINGS[@]} -gt 0 ]; then
        echo ""
        echo "  ${BOLD}Warnings:${RESET}"
        for w in "${WARNINGS[@]}"; do
            echo "  ${YELLOW}[!!]${RESET} $w"
        done
    fi

    echo ""
    echo "  ${BOLD}Commands:${RESET}"
    echo "    sudo systemctl start pihome    Start PiHome now"
    echo "    sudo systemctl status pihome   Check service status"
    echo "    sudo systemctl stop pihome     Stop the service"
    echo "    sudo systemctl restart pihome  Restart the service"
    echo "    tail -f ${PIHOME_DIR}/pihome.log   View live logs"
    echo ""
    echo "  ${DIM}Full install log: ${LOG_FILE}${RESET}"
}

# -----------------------------------------------------------------------------
# CLI Argument Parsing
# -----------------------------------------------------------------------------
print_usage() {
    echo "Usage: install.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --clean          Remove install state and start fresh"
    echo "  --skip-airplay   Skip AirPlay (shairport-sync) installation"
    echo "  --verbose        Show command output in terminal"
    echo "  --unattended     Skip all confirmation prompts"
    echo "  --help           Show this help message"
}

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --clean)
                rm -f "$STATE_FILE"
                ;;
            --skip-airplay)
                SKIP_AIRPLAY=true
                ;;
            --verbose)
                VERBOSE=true
                ;;
            --unattended)
                UNATTENDED=true
                ;;
            --help)
                print_usage
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                print_usage
                exit 1
                ;;
        esac
        shift
    done
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
main() {
    parse_args "$@"
    print_banner
    preflight_checks

    echo "  This will install PiHome to ${BOLD}${PIHOME_DIR}${RESET}"
    echo "  Installation log: ${DIM}${LOG_FILE}${RESET}"
    echo ""

    if ! confirm "Continue with installation? [Y/n]" "y"; then
        echo "  Installation cancelled."
        exit 0
    fi

    phase_setup_directories      # 1/9
    phase_clone_repository       # 2/9
    phase_system_dependencies    # 3/9
    phase_build_sdl2             # 4/9
    phase_build_airplay          # 5/9
    phase_python_dependencies    # 6/9
    phase_configure_environment  # 7/9
    phase_boot_splash            # 8/9
    phase_install_service        # 9/9

    # Clean up state file on success
    rm -f "$STATE_FILE"

    print_summary

    echo ""
    if confirm "Reboot now to apply all changes? [y/N]" "n"; then
        echo "  Rebooting..."
        sudo reboot
    else
        echo "  ${DIM}Remember to reboot before starting PiHome.${RESET}"
        echo ""
    fi
}

main "$@"

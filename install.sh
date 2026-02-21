#!/bin/bash
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}Installing vimview...${NC}"

# 1. Determine where to install
REPO_DIR="$HOME/.local/share/vimview"
BIN_DIR="$HOME/.local/bin"
ICON_DEST="$HOME/.local/share/icons/hicolor/128x128/apps"
DESKTOP_DIR="$HOME/.local/share/applications"

# 2. Clone or update the repository
REPO_URL="https://github.com/yourusername/vimview"
TAG="main"  # or "master"

if command -v git &> /dev/null; then
    if [ -d "$REPO_DIR" ]; then
        echo "Updating existing installation with git..."
        git -C "$REPO_DIR" pull
    else
        echo "Cloning repository with git..."
        git clone --depth 1 "$REPO_URL" "$REPO_DIR"
    fi
else
    echo "git not found, downloading repository as zip..."
    mkdir -p "$REPO_DIR"
    TMP_ZIP="/tmp/vimview.zip"
    if command -v wget &> /dev/null; then
        wget -O "$TMP_ZIP" "$REPO_URL/archive/$TAG.zip"
    elif command -v curl &> /dev/null; then
        curl -L -o "$TMP_ZIP" "$REPO_URL/archive/$TAG.zip"
    else
        echo -e "${RED}Neither git, wget, nor curl found. Cannot download repository.${NC}"
        exit 1
    fi
    unzip -q "$TMP_ZIP" -d /tmp
    cp -r "/tmp/vimview-$TAG"/* "$REPO_DIR"
    rm -rf "/tmp/vimview-$TAG" "$TMP_ZIP"
fi

# 3. Locate the pre‑built binary
BINARY_SRC="$REPO_DIR/dist/vimview"
if [ ! -f "$BINARY_SRC" ]; then
    echo -e "${RED}Pre‑built binary not found at $BINARY_SRC. Falling back to source installation.${NC}"
    # Fallback: use the Python script directly (requires Python and PySide6)
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Python3 not found. Cannot fallback. Aborting.${NC}"
        exit 1
    fi
    pip3 install --user --upgrade PySide6
    cat > "$BIN_DIR/vimview" << EOF
#!/bin/bash
exec python3 "$REPO_DIR/main.py" "\$@"
EOF
    chmod +x "$BIN_DIR/vimview"
    echo -e "${GREEN}Source installation complete.${NC}"
else
    # 4. Install the binary
    mkdir -p "$BIN_DIR"
    cp "$BINARY_SRC" "$BIN_DIR/vimview"
    chmod +x "$BIN_DIR/vimview"
    echo "Installed binary to $BIN_DIR/vimview"
fi

# 5. Add ~/.local/bin to PATH if not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.zshrc" 2>/dev/null || true
    export PATH="$HOME/.local/bin:$PATH"
fi

# 6. Install icon (if present)
if [ -f "$REPO_DIR/icon.png" ]; then
    mkdir -p "$ICON_DEST"
    cp "$REPO_DIR/icon.png" "$ICON_DEST/vimview.png"
    echo "Icon installed to $ICON_DEST/vimview.png"
    ICON_PATH="$ICON_DEST/vimview.png"
else
    ICON_PATH="image-x-generic"
fi

# 7. Create desktop entry
mkdir -p "$DESKTOP_DIR"
cat > "$DESKTOP_DIR/vimview.desktop" << EOF
[Desktop Entry]
Type=Application
Name=vimview
Comment=Vim‑inspired image viewer
Exec=$BIN_DIR/vimview %F
Icon=$ICON_PATH
Terminal=false
Categories=Graphics;Viewer;
MimeType=image/png;image/jpeg;image/gif;image/bmp;image/webp;
StartupNotify=true
EOF

update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true

echo -e "${GREEN}Installation complete!${NC}"
echo "You can now run 'vimview' from the terminal or find it in your application menu."

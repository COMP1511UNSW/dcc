#!/usr/bin/env bash

HOME_PATH=~
INSTALL_PATH="${HOME_PATH}/.dcc"

if [[ `uname` = MINGW* ]] || [[ `uname` = MSYS* ]]; then
    if [[ $MSYS2_PATH_TYPE != 'inherit' ]]; then
        setx MSYS2_PATH_TYPE inherit
        echo Updated! Please restart your terminal and rerun this script to install dcc.
    fi
fi

function report_missing_gdb () {
    if [[ `uname` = Darwin ]]; then
        echo "Missing gdb on path, see: https://sourceware.org/gdb/wiki/PermissionsDarwin."
    elif [[ `uname` = MINGW* ]] || [[ `uname` = MSYS* ]]; then
        echo "Git not found. Please run \"pacman -S python --noconfirm;\" in the terminal and then reinstall"
    elif [[ `uname` = Linux ]]; then
        echo "Please install git using your package manager For example: sudo apt install python"
    fi
    exit 1
}

function report_missing_python3 () {
    if [[ `uname` = Darwin ]]; then
        echo "python3 not found on path, ensure python3 is available."
    elif [[ `uname` = MINGW* ]] || [[ `uname` = MSYS* ]]; then
        echo "Git not found. Please run \"pacman -S python --noconfirm;\" in the terminal and then reinstall"
    elif [[ `uname` = Linux ]]; then
        echo "Please install git using your package manager For example: sudo apt install python"
    fi
    exit 1
}

command -v python3 >/dev/null 2>&1 || report_missing_python3
command -v gdb >/dev/null 2>&1 || report_missing_gdb

if [ -d "${INSTALL_PATH}" ]; then
    echo "Looks like you already have dcc installed!"
    echo "To uninstall run \"rm -rf ${INSTALL_PATH}\""
    exit 1
fi

sudo mkdir "$INSTALL_PATH"
sudo curl -L https://github.com/COMP1511UNSW/dcc/releases/latest/download/dcc -o "$INSTALL_PATH/dcc"
sudo chmod +x "$INSTALL_PATH/dcc"

# Add to .bashrc if using bash
if [ ${SHELL} = "/bin/bash" ]; then
    echo "export PATH=\"$INSTALL_PATH:\$PATH\"" >> ~/.bash_profile
    echo "export PATH=\"$INSTALL_PATH:\$PATH\"" >> ~/.bashrc
fi

# Add to .zshrc if using zsh
if [ ${SHELL} = "/bin/zsh" ]; then
    echo "export PATH=\"$INSTALL_PATH:\$PATH\"" >> ~/.zshrc
fi

export PATH="$INSTALL_PATH:$PATH"

if [[ `uname` = MINGW32* ]]; then
    #Export to path -- for current terminal
    export PATH="$HOME/.dcc/dcc:$PATH"

    #Export path for new terminals
    export ORIGINAL_PATH="$HOME/.dcc/dcc:$ORIGINAL_PATH"

    # Set path
    setx PATH "$ORIGINAL_PATH"
fi

if [[ `uname` = MINGW64* ]] || [[ `uname` = MSYS* ]]; then
    #Export to path -- for current terminal
    export PATH="$HOME/.dcc/dcc:$PATH"

    #Export path for new terminals
    export ORIGINAL_PATH="$HOME/.dcc/dcc:$ORIGINAL_PATH"

    # Set path
    setx PATH "$ORIGINAL_PATH"
fi

echo "DCC Successfully installed! Please restart your terminal..."
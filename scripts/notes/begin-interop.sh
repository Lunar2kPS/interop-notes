#!/bin/bash
# NOTE: YOU MUST SOURCE THIS SCRIPT! (Instead of running it directly).

function getURLFromSSH() {
    local arg1=$1
    echo "$arg1" \
        | sed -e 's|:|/|g' \
            -e 's|ssh///||g' \
            -e 's|git@|https://|g' \
            -e 's|\.git$||'
}

# NOTE: These are ANSI escape codes to control text color in the terminal.
BLUE="\e[34m"
RESET_COLOR="\e[0m"
printf "${BLUE}Setting up interop SSH key...\n${RESET_COLOR}"

privateKeyPath="./interop_key_ed25519"
eval "$(ssh-agent -s)"
ssh-add "$privateKeyPath"
ssh -T git@github.com

read -s -p "Enter the repository URL: " sshURL
printf "\n"
git clone -q $sshURL &>/dev/null
exitCode=$?
if [ $exitCode -eq 0 ]; then
    echo "Changing directory..."
    url=$(getURLFromSSH "$sshURL")
    folderName="$(basename $url)"
    folderName="${folderName%.*}"
    cd "$folderName" &>/dev/null
    unset url
    unset folderName
fi
unset sshURL

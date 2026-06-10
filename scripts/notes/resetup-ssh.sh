#!/bin/bash

# NOTE: These are ANSI escape codes to control text color in the terminal.
BLUE="\e[34m"
RESET_COLOR="\e[0m"
printf "${BLUE}Setting up GitHub SSH key...\n${RESET_COLOR}"

privateKeyPath="C:/dev/keys/id_ed25519"
eval "$(ssh-agent -s)"
ssh-add "$privateKeyPath"
ssh -T git@github.com

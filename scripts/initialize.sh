#!/bin/bash
printf "Setting git user.name and user.email locally...\n"
git config --local user.name "Carlos DaLomba"
git config --local user.email "carlos@2kpixelstudios.net"

cp ./scripts/replace-names/.env.example ./scripts/replace-names/.env

printf "Remember to update your ./scripts/replace-names/.env file, and run the following after you're finished adding your files:\n    python ./scripts/replace-names/main.py\n"

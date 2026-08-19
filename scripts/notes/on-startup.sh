#!/bin/bash

# Use Win + R, "shell:startup".
# Create a new shortcut, enter in:
#   "C:\Program Files\Git\bin\bash.exe" --login -i -c "C:/dev/scripts/on-startup.sh"; exit
echo "Custom Git Bash auto-startup commands starting..."

autoOpenFolders=(
    "C:/dev"
    "C:/dev/projects/example-1"
    "C:/dev/projects/example-2"
)

for folder in "${autoOpenFolders[@]}"; do
    code "$folder"
done

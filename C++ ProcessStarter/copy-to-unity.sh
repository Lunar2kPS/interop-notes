#!/bin/bash
projectName="ProcessStarter"
extensions=(
    ".dll"
    ".pdb"
)
fromFolder="./out/Debug"
toFolder="../../Assets/Plugins/Process Starter/win32/x64"
count=0
failedCount=0
for filePath in "${fromFolder}"/*; do
    for extension in "${extensions[@]}"; do
        pattern="$extension\$"
        if [[ "$filePath" =~ $pattern ]]; then
            fileName="$(basename "$filePath")"
            cp "$filePath" "$toFolder/$fileName"
            exitCode=$?
            if [ $exitCode -eq 0 ]; then
                printf "  + $fileName\n"
                count=$((count + 1))
            else
                failedCount=$((failedCount + 1))
                printf "\n"
            fi
            break
        fi
    done
done
printf "\n"

if ((count > 0)); then
    printf "Copied $count file(s) to $toFolder.\n"
fi
if ((failedCount > 0)); then
    printf "$failedCount file(s) were unable to be copied. Do you need to close Unity?\n"
fi

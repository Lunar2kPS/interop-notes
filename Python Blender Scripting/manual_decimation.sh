#!/bin/bash
# COMMAND-LINE USAGE:
#   ./helpers/manual_decimation.sh --input-folder PATH --output-folder PATH

argCount=$#
args=("$@")

maxConcurrent=2
running=0

for ((i = 0; i < argCount; i = i + 2)); do
    currentArg="${args[$i]}"
    nextArg="${args[(($i + 1))]}"
    case "$currentArg" in
        "--input-folder") inputFolder="$nextArg" ;;
        "--output-folder") outputFolder="$nextArg" ;;
        "--blender-log-file") blenderLogFile="$nextArg" ;;
    esac
done

if [ -z "$inputFolder" ] || [ -z "$outputFolder" ]; then
    printf -- "--input-folder and --output-folder args are required.\n" >&2
    exit 1
fi

thisScriptFolder="$(dirname "${BASH_SOURCE[0]}")"
for filePath in "$inputFolder/"*.glb; do
    if [ ! -f "$filePath" ]; then
        continue
    fi
    fileName="$(basename "$filePath")"
    fileNameWithoutExtension="${fileName%%.*}" # NOTE: Bash parameter expansion, of the form ${variable<operator>pattern}, and %% Removes the longest pattern from the end of the string, .* picks up a period and everything after it.
    fileExtension="${fileName##*.}"
    outFilePath="$outputFolder/$fileName"

    perLogFile="${blenderLogFile//\$fileName/$fileNameWithoutExtension}"
    python "$thisScriptFolder/manual_decimation_main.py" --input-file "$filePath" --output-file "$outFilePath" --blender-log-file "$perLogFile" &
    ((running++))
    if ((running >= maxConcurrent)); then
        wait -n # NOTE: This waits for the first of any of the PIDs started by this script/shell to finish.
        ((running--))
    fi
done

wait # NOTE: This waits for the rest to complete.

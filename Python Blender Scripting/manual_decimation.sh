#!/bin/bash
# COMMAND-LINE USAGE:
#   ./helpers/manual_decimation.sh --input-folder PATH --output-folder PATH

argCount=$#
args=("$@")

maxConcurrent=3
running=0

for ((i = 0; i < argCount; i = i + 2)); do
    currentArg="${args[$i]}"
    nextArg="${args[(($i + 1))]}"
    case "$currentArg" in
        "--input-folder") inputFolder="$nextArg" ;;
        "--output-folder") outputFolder="$nextArg" ;;
    esac
done

if [ -z "$inputFolder" ] || [ -z "$outputFolder" ]; then
    printf -- "--input-folder and --output-folder args are required.\n" >&2
    exit 1
fi

thisScriptFolder="$(dirname ${BASH_SOURCE[0]})"
for filePath in "$inputFolder/"*; do
    fileName="$(basename "$filePath")"
    fileNameWithoutExtension="${fileName%%.*}" # NOTE: Bash parameter expansion, of the form ${variable<operator>pattern}, and %% Removes the longest pattern from the end of the string, .* picks up a period and everything after it.
    outFilePath="$outputFolder/$fileName"

    python "$thisScriptFolder/manual_decimation_main.py" --input-file "$filePath" --output-file "$outFilePath" --blender-log-file "blender_output_$fileNameWithoutExtension.log" &
    ((running++))
    if ((running >= maxConcurrent)); then
        wait -n # NOTE: This waits for the first of any of the PIDs started by this script/shell to finish.
        ((running--))
    fi
done

wait # NOTE: This waits for the rest to complete.

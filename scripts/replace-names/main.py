from pathlib import Path
from dotenv import load_dotenv
import re
import os

def main():
    load_dotenv()
    fromPatterns = [re.compile(x) for x in os.getenv("FROM_PATTERNS").split(";")]
    toValues = os.getenv("TO_VALUES").split(";")

    fromFileNamePatterns = [re.compile(x) for x in os.getenv("FROM_FILE_NAME_PATTERNS").split(";")]
    toFileNameValues = os.getenv("TO_FILE_NAME_VALUES").split(";")

    ignorePatterns = [re.compile(x) for x in os.getenv("IGNORE_PATTERNS").split(";")]
    filePattern = re.compile(os.getenv("FILE_PATTERN"))
    for path in Path(os.getenv("ROOT_FOLDER")).rglob("*"):
        if path.is_file() and filePattern.match(path.name):
            skip = False
            for ignore in ignorePatterns:
                if ignore.match(path.as_posix()):
                    skip = True
                    break
            if skip:
                continue

            try:
                fileText = path.read_text(encoding="utf-8")
                newText = fileText
                for (prev, next) in zip(fromPatterns, toValues):
                    newText = prev.sub(next, newText)

                newPathStr = path.as_posix()
                for (prevName, nextName) in zip(fromFileNamePatterns, toFileNameValues):
                    newPathStr = prevName.sub(nextName, newPathStr)
                newPath = Path(newPathStr)
                pathChanged = newPathStr != path.as_posix()

                if newText != fileText or pathChanged:
                    newPath.write_text(newText, encoding="utf-8")
                    print(f"Updated: {path.as_posix()}" + (f" → {newPath.as_posix()}" if pathChanged else ""))
                    if pathChanged:
                        path.unlink()
            except UnicodeDecodeError as u:
                print(f"Failed to decode file at {path.as_posix()}: {u.reason}")

main()

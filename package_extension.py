"""
Package the Lomba Chrome Extension into a clean zip archive for distribution.
"""
import os
import zipfile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EXTENSION_DIR = os.path.join(BASE_DIR, "extension")
OUTPUT_ZIP = os.path.join(BASE_DIR, "lomba-extension.zip")

def package():
    if not os.path.isdir(EXTENSION_DIR):
        print(f"Error: {EXTENSION_DIR} not found.")
        return

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(EXTENSION_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, EXTENSION_DIR)
                zf.write(file_path, arcname)

    print(f"Successfully packaged extension to: {OUTPUT_ZIP}")

if __name__ == "__main__":
    package()

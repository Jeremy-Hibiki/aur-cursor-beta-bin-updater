import sys
import json
import os
import base64
import hashlib
import requests

DEBUG = os.environ.get("DEBUG", "false").lower() == "true"


def debug_print(*args, **kwargs):
    if DEBUG:
        print(*args, **kwargs)


def base64_to_hex(base64_string):
    return base64.b64decode(base64_string).hex()


def calculate_sha512(url):
    """Download file and calculate its SHA512."""
    print("::debug::Downloading file to calculate SHA512...")
    response = requests.get(url, stream=True)
    response.raise_for_status()

    sha512_hash = hashlib.sha512()
    for chunk in response.iter_content(chunk_size=8192):
        sha512_hash.update(chunk)

    return sha512_hash.hexdigest()


def update_pkgbuild(pkgbuild_lines, json_data):
    new_version = json_data["new_version"]
    new_rel = json_data["new_rel"]
    new_commit = json_data["new_commit"]

    # Calculate SHA512 for the new AppImage
    appimage_url = f"https://downloads.cursor.com/production/{new_commit}/linux/x64/Cursor-{new_version}-x86_64.AppImage"
    appimage_sha512 = calculate_sha512(appimage_url)
    debug_print(f"Calculated AppImage SHA512: {appimage_sha512}")

    updated_lines = []
    in_sha = False

    for line in pkgbuild_lines:
        if line.startswith("pkgver="):
            updated_lines.append(f"pkgver={new_version}\n")
        elif line.startswith("pkgrel="):
            updated_lines.append(f"pkgrel={new_rel}\n")
        elif line.startswith("_commit="):
            updated_lines.append(f"_commit={new_commit}\n")
        elif line.startswith("source="):
            # Update the source line with the new commit and version
            updated_lines.append(f'source=("${{_appimage}}::https://downloads.cursor.com/production/{new_commit}/linux/x64/Cursor-{new_version}-x86_64.AppImage"\n')
        elif line.startswith("https://gitlab.archlinux.org"):
            # This is the second source line (code.sh)
            updated_lines.append(line)
        elif line.startswith("sha512sums="):
            updated_lines.append(f"sha512sums=('{appimage_sha512}'\n")
            in_sha = True
        elif in_sha and line.strip().endswith(")"):
            # This is the last line of sha512sums, add the second checksum
            updated_lines.append(f"            '937299c6cb6be2f8d25f7dbc95cf77423875c5f8353b8bd6cd7cc8e5603cbf8405b14dbf8bd615db2e3b36ed680fc8e1909410815f7f8587b7267a699e00ab37')\n")
            in_sha = False
        elif not in_sha:
            updated_lines.append(line)

    return updated_lines


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python update_pkgbuild.py <check_output_file>")
        sys.exit(1)

    debug_print(f"Reading check output from {sys.argv[1]}")
    with open(sys.argv[1], "r") as f:
        check_output = json.load(f)

    debug_print(f"Check output content: {json.dumps(check_output, indent=2)}")

    if check_output["update_needed"]:
        debug_print("Update needed, reading current PKGBUILD")
        with open("PKGBUILD", "r") as f:
            current_pkgbuild = f.readlines()

        debug_print("Calling update_pkgbuild()")
        updated_pkgbuild = update_pkgbuild(current_pkgbuild, check_output)

        # Write the changes to the file
        with open("PKGBUILD", "w") as f:
            f.writelines(updated_pkgbuild)
        debug_print(
            f"PKGBUILD updated to version {check_output['new_version']} (release {check_output['new_rel']}) with commit {check_output['new_commit']}"
        )
    else:
        print("No update needed.")

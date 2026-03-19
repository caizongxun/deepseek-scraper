"""
Run this once to find msedgedriver.exe anywhere on this machine.
Result is saved to driver_path.txt and used by scraper.py automatically.

Usage:
    python find_driver.py
"""
import os
import subprocess
import sys

PATH_FILE = "driver_path.txt"


def search_with_where() -> str | None:
    """Use Windows where.exe - fast, searches PATH."""
    try:
        result = subprocess.run(
            ["where", "msedgedriver"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            path = result.stdout.strip().splitlines()[0]
            if os.path.exists(path):
                return path
    except Exception:
        pass
    return None


def search_with_glob(roots: list) -> str | None:
    """Walk common directories recursively."""
    import glob
    patterns = [
        r"C:\Program Files*\Microsoft\Edge*\**\msedgedriver.exe",
        r"C:\Users\*\AppData\Local\Microsoft\Edge*\**\msedgedriver.exe",
        r"C:\Users\*\.wdm\**\msedgedriver.exe",
        r"C:\ProgramData\**\msedgedriver.exe",
    ]
    for pat in patterns:
        matches = glob.glob(pat, recursive=True)
        if matches:
            return sorted(matches)[-1]
    return None


def search_full_walk(drive: str = "C:\\") -> str | None:
    """Last resort: walk entire C:\ (slow, ~1-2 min)."""
    print(f"[Scan] Walking {drive} ... this may take 1-2 minutes")
    for root, dirs, files in os.walk(drive):
        # Skip noise
        dirs[:] = [d for d in dirs if d not in (
            "Windows", "$Recycle.Bin", "System Volume Information",
            "WinSxS", "Temp", "tmp"
        )]
        if "msedgedriver.exe" in files:
            return os.path.join(root, "msedgedriver.exe")
    return None


def main():
    print("[1] Checking PATH with where.exe ...")
    path = search_with_where()
    if path:
        print(f"    Found: {path}")
    else:
        print("    Not on PATH")
        print("[2] Searching common directories ...")
        path = search_with_glob([])
        if path:
            print(f"    Found: {path}")
        else:
            print("    Not found in common dirs")
            print("[3] Full C:\\ scan (slow) ...")
            path = search_full_walk()
            if path:
                print(f"    Found: {path}")

    if path:
        with open(PATH_FILE, "w") as f:
            f.write(path)
        print(f"\n[OK] Saved to {PATH_FILE}")
        print(f"     Path: {path}")
        print("\nRe-run python app.py now - scraper will use this driver automatically.")
    else:
        print("\n[FAIL] msedgedriver.exe not found on this machine.")
        print("Download it manually from:")
        print("  https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
        print("Match the version shown in Edge > Help > About Microsoft Edge")
        print("Then place msedgedriver.exe in this project folder and re-run.")
        sys.exit(1)


if __name__ == "__main__":
    main()

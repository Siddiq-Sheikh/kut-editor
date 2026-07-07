import os
import subprocess
import sys

def main():
    print("Building Kut Video Editor...")
    
    try:
        command = [
            "pyinstaller", "--clean", "--noconsole", "--onedir",
            "--icon=assets/kut.ico", "--add-data", "assets;assets",
            "kut.py"
        ]
        subprocess.run(command, check=True)
        print("\nBuild completed successfully!")
        print("Executable can be found in the dist/kut directory.")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error code: {e.returncode}")
    except FileNotFoundError:
        print("\nPyInstaller not found. Please make sure it is installed: pip install pyinstaller")

if __name__ == "__main__":
    main()

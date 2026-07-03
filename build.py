import os
import subprocess
import sys

def main():
    print("Building Kut Video Editor...")
    
    if not os.path.exists("kut.spec"):
        print("Error: kut.spec not found in current directory.")
        sys.exit(1)
        
    try:
        subprocess.run(["pyinstaller", "--clean", "-y", "kut.spec"], check=True)
        print("\nBuild completed successfully!")
        print("Executable can be found in the dist/kut directory.")
    except subprocess.CalledProcessError as e:
        print(f"\nBuild failed with error code: {e.returncode}")
    except FileNotFoundError:
        print("\nPyInstaller not found. Please make sure it is installed: pip install pyinstaller")

if __name__ == "__main__":
    main()

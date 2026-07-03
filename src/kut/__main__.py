import sys
from .editor import Kut

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else None
    Kut(video_path=path).run()

if __name__ == "__main__":
    main()

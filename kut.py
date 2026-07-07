import os
import sys

# Ensure src is in the path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))

from src.kut.__main__ import main

if __name__ == '__main__':
    main()

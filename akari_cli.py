import sys
import os

# Tambahkan folder akari_cli ke path agar bisa diimport
sys.path.append(os.path.join(os.path.dirname(__file__), "akari_cli"))

from akari_cli.akari_cli import main

if __name__ == "__main__":
    main()

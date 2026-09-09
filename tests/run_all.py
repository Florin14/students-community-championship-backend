"""Run every test module. Each one builds its own database, so they run as
separate processes.

    .venv/bin/python tests/run_all.py
"""
import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    modules = sorted(glob.glob(os.path.join(HERE, "test_*.py")))
    if not modules:
        print("no test modules found")
        return 1

    failed = []
    for path in modules:
        name = os.path.basename(path)
        result = subprocess.run([sys.executable, path])
        if result.returncode != 0:
            failed.append(name)

    print("\n" + "=" * 70)
    if failed:
        print("FAILED modules: %s" % ", ".join(failed))
        return 1
    print("%d module(s) passed" % len(modules))
    return 0


if __name__ == "__main__":
    sys.exit(main())

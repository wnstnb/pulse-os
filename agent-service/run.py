import os
import sys


def _bootstrap():
    service_root = os.path.dirname(__file__)
    src_path = os.path.join(service_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def main():
    _bootstrap()
    from x_agent_os.run import main as runner

    runner()


if __name__ == "__main__":
    main()

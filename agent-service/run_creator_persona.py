import argparse
import json
import os
import sys


def _bootstrap():
    service_root = os.path.dirname(__file__)
    src_path = os.path.join(service_root, "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)


def main():
    _bootstrap()
    from x_agent_os.creator_persona import CreatorPersonaInspo

    parser = argparse.ArgumentParser(description="Creator Persona Inspo")
    parser.add_argument("--username", required=True)
    parser.add_argument("--window-days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--top-n", type=int, default=7)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    runner = CreatorPersonaInspo()
    result = runner.run(
        handle=args.username,
        window_days=args.window_days,
        limit=args.limit,
        top_n=args.top_n,
        force=args.force,
    )
    print(json.dumps(result.__dict__))


if __name__ == "__main__":
    main()

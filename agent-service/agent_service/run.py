import argparse

from agent_service.orchestrator import run_daily_pipeline, run_metrics_update


def main():
    parser = argparse.ArgumentParser(description="X Agent OS runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    daily_parser = subparsers.add_parser("daily", help="Run daily pipeline + brief")
    daily_parser.add_argument("--date", help="Override date YYYY-MM-DD", default=None)

    metrics_parser = subparsers.add_parser("metrics", help="Run metrics update")
    metrics_parser.add_argument("--days", type=int, default=14)

    args = parser.parse_args()

    if args.command == "daily":
        result = run_daily_pipeline(date=args.date)
        print(f"Daily pipeline complete: {result}")
    elif args.command == "metrics":
        result = run_metrics_update(days=args.days)
        print(f"Metrics update complete: {result}")


if __name__ == "__main__":
    main()

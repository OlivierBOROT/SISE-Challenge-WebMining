"""Entry point for running the app with simple CLI flags.

Usage examples:
  python run.py --dev -f data/live.db
  python run.py --prod
  python run.py            # defaults to production
"""

import argparse

from app import create_app


def main():
    parser = argparse.ArgumentParser(
        description="Run the web app with environment flags"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--dev", action="store_true", help="Run in development mode")
    group.add_argument("--prod", action="store_true", help="Run in production mode")
    parser.add_argument(
        "-f", "--file", dest="data_file", help="Path to data file for runtime storage"
    )
    args = parser.parse_args()

    # Mode selection
    if args.dev:
        print("dev lancé")
        debug = True
    else:
        # --prod or default
        print("prod lancé")
        debug = False

    # Data file info
    if args.data_file:
        print(f"Data file: {args.data_file}")
    else:
        print("No data file provided")

    app = create_app()
    # Print mode in runtime
    print(f"App mode: {'dev' if debug else 'prod'}")
    if args.data_file:
        print(f"Using data file: {args.data_file}")

    # Run the server
    app.run(debug=debug, port=8000)


if __name__ == "__main__":
    main()

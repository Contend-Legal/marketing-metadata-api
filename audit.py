import json
import argparse
import sys
from typing import Optional, Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from models import AuditReport
from fetch import build_gtm_accounts, build_ga_accounts
from presenters import print_text_report, print_json_report, save_report


# --- Constants ---
CONFIG_PATH = "config.json"
DEFAULT_OUTPUT_DIR = "outputs"
SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]


# --- Configuration & Authentication ---
def load_config(path: str) -> dict[str, Any]:
    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Error: Configuration file not found at '{path}'.", file=sys.stderr)
        return {}
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return {}


def get_credentials(credentials_path: str) -> Optional[service_account.Credentials]:
    try:
        return service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
    except FileNotFoundError:
        print(
            f"Error: Credentials file not found at '{credentials_path}'.",
            file=sys.stderr,
        )
        return None
    except Exception as e:
        print(f"An error occurred during authentication: {e}", file=sys.stderr)
        return None


# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(
        description="Audit Google Marketing Platform configurations."
    )
    parser.add_argument(
        "--json", action="store_true", help="Output the report in JSON format."
    )
    parser.add_argument(
        "--output",
        "-o",
        metavar="DIR",
        nargs="?",
        const=DEFAULT_OUTPUT_DIR,
        help=f"Save report to file in specified directory (default: {DEFAULT_OUTPUT_DIR}/).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed progress."
    )
    parser.add_argument(
        "--quiet", "-q", action="store_true", help="Suppress status messages."
    )
    args = parser.parse_args()

    # Set up logging function based on verbosity
    def log(msg: str) -> None:
        if args.verbose and not args.quiet:
            print(msg)

    def status(msg: str) -> None:
        if not args.quiet:
            print(msg)

    config = load_config(CONFIG_PATH)
    credentials_path = config.get("credentials_path")
    if not credentials_path:
        print("Error: 'credentials_path' not found in configuration.", file=sys.stderr)
        return 1

    creds = get_credentials(credentials_path)
    if not creds:
        return 1

    try:
        gtm_service = build("tagmanager", "v2", credentials=creds)
        ga_admin_service = build("analyticsadmin", "v1beta", credentials=creds)

        status("Fetching GTM data...")
        gtm_accounts = build_gtm_accounts(gtm_service, log=log)

        status("Fetching GA4 data...")
        ga_accounts = build_ga_accounts(ga_admin_service, log=log)

        report = AuditReport(gtm_accounts=gtm_accounts, ga_accounts=ga_accounts)

        # Output handling
        if args.output:
            filepath = save_report(report, args.output, as_json=args.json)
            status(f"Report saved to: {filepath}")
        else:
            if args.json:
                print_json_report(report)
            else:
                print_text_report(report)

        return 0

    except HttpError as e:
        print(f"An API HTTP error occurred: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

import json
import argparse
from typing import Optional, Any

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from models import AuditReport
from fetch import build_gtm_accounts, build_ga_accounts
from presenters import print_text_report, print_json_report


# --- Constants ---
CONFIG_PATH = "config.json"
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
        print(f"Error: Configuration file not found at '{path}'.")
        return {}
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return {}


def get_credentials(credentials_path: str) -> Optional[service_account.Credentials]:
    try:
        return service_account.Credentials.from_service_account_file(
            credentials_path, scopes=SCOPES
        )
    except FileNotFoundError:
        print(f"Error: Credentials file not found at '{credentials_path}'.")
        return None
    except Exception as e:
        print(f"An error occurred during authentication: {e}")
        return None


# --- Main Execution ---
def main():
    parser = argparse.ArgumentParser(
        description="Audit Google Marketing Platform configurations."
    )
    parser.add_argument(
        "--json", action="store_true", help="Output the report in JSON format."
    )
    args = parser.parse_args()

    config = load_config(CONFIG_PATH)
    credentials_path = config.get("credentials_path")
    if not credentials_path:
        print("Error: 'credentials_path' not found in configuration.")
        return

    creds = get_credentials(credentials_path)
    if not creds:
        return

    try:
        gtm_service = build("tagmanager", "v2", credentials=creds)
        ga_admin_service = build("analyticsadmin", "v1beta", credentials=creds)

        print("Fetching GTM data...")
        gtm_accounts = build_gtm_accounts(gtm_service)

        print("Fetching GA4 data...")
        ga_accounts = build_ga_accounts(ga_admin_service)

        report = AuditReport(gtm_accounts=gtm_accounts, ga_accounts=ga_accounts)

        if args.json:
            print_json_report(report)
        else:
            print_text_report(report)

    except HttpError as e:
        print(f"An API HTTP error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    main()

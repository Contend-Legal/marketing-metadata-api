import json
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Load configuration
with open("config.json", "r") as f:
    config = json.load(f)

# Define the scopes required for the APIs
SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]


def get_credentials():
    """Authenticates using the service account file."""
    try:
        return service_account.Credentials.from_service_account_file(
            config["credentials_path"], scopes=SCOPES
        )
    except FileNotFoundError:
        print(f"Error: Credentials file not found at '{config['credentials_path']}'.")
        print("Please ensure 'config.json' points to your service account key file.")
        return None
    except Exception as e:
        print(f"An error occurred during authentication: {e}")
        return None


def get_gtm_data(service):
    """Fetches and prints GTM account and container data."""
    try:
        accounts = service.accounts().list().execute()
        print("--- Google Tag Manager ---")
        if "account" in accounts:
            for account in accounts["account"]:
                print(f"\n[GTM Account] {account['name']} (ID: {account['accountId']})")

                containers = (
                    service.accounts()
                    .containers()
                    .list(parent=account["path"])
                    .execute()
                )
                if "container" in containers:
                    for container in containers["container"]:
                        print(
                            f"  - [Container] {container['name']} (Public ID: {container['publicId']})"
                        )
                else:
                    print("  - No containers found.")
        else:
            print("No GTM accounts found or accessible by the service account.")
        print("\n" + "=" * 40 + "\n")

    except HttpError as e:
        print(f"An HTTP error occurred with GTM API: {e}")
    except Exception as e:
        print(f"An error occurred fetching GTM data: {e}")


def get_ga_data(service):
    """Fetches and prints GA4 account, property, and data stream data."""
    try:
        accounts = service.accounts().list().execute()
        print("--- Google Analytics (GA4) ---")
        if "accounts" in accounts:
            for account in accounts["accounts"]:
                print(
                    f"\n[GA Account] {account['displayName']} (ID: {account['name'].split('/')[1]})"
                )

                properties = (
                    service.properties()
                    .list(filter=f"parent:{account['name']}")
                    .execute()
                )
                if "properties" in properties:
                    for prop in properties["properties"]:
                        print(
                            f"  - [Property] {prop['displayName']} (ID: {prop['name'].split('/')[1]})"
                        )

                        streams = (
                            service.properties()
                            .dataStreams()
                            .list(parent=prop["name"])
                            .execute()
                        )
                        if "dataStreams" in streams:
                            for stream in streams["dataStreams"]:
                                stream_type = stream["type"].replace("_DATA_STREAM", "")
                                measurement_id = stream.get("webStreamData", {}).get(
                                    "measurementId", "N/A"
                                )
                                print(
                                    f"    - [Stream] {stream['displayName']} ({stream_type}) - Measurement ID: {measurement_id}"
                                )
                        else:
                            print("    - No data streams found.")
                else:
                    print("  - No properties found.")
        else:
            print("No GA accounts found or accessible by the service account.")

    except HttpError as e:
        print(f"An HTTP error occurred with GA API: {e}")
    except Exception as e:
        print(f"An error occurred fetching GA data: {e}")


def main():
    """Main function to orchestrate the audit."""
    creds = get_credentials()
    if not creds:
        return

    # Build API services
    gtm_service = build("tagmanager", "v2", credentials=creds)
    ga_admin_service = build("analyticsadmin", "v1beta", credentials=creds)

    # Fetch and display data
    get_gtm_data(gtm_service)
    get_ga_data(ga_admin_service)


if __name__ == "__main__":
    main()

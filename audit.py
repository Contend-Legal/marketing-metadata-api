import json
import argparse
from typing import Optional, Any

from pydantic import BaseModel, Field
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Constants ---

CONFIG_PATH = "config.json"
DEFAULT_WORKSPACE_ID = "1"
SCOPES = [
    "https://www.googleapis.com/auth/tagmanager.readonly",
    "https://www.googleapis.com/auth/analytics.readonly",
]

# --- Data Models ---

class GtmTag(BaseModel):
    name: str
    tag_id: str = Field(..., alias="tagId")
    type: str
    parameters: Optional[list[dict[str, Any]]] = None

class GtmContainer(BaseModel):
    name: str
    public_id: str = Field(..., alias="publicId")
    container_id: str = Field(..., alias="containerId")
    tags: list[GtmTag] = Field(default_factory=list)

class GtmAccount(BaseModel):
    name: str
    account_id: str = Field(..., alias="accountId")
    containers: list[GtmContainer] = Field(default_factory=list)

class GaDataStream(BaseModel):
    display_name: str = Field(..., alias="displayName")
    type: str
    measurement_id: Optional[str] = None

class GaProperty(BaseModel):
    display_name: str = Field(..., alias="displayName")
    property_id: str
    time_zone: str = Field(..., alias="timeZone")
    currency_code: str = Field(..., alias="currencyCode")
    data_streams: list[GaDataStream] = Field(default_factory=list, alias="dataStreams")

class GaAccount(BaseModel):
    display_name: str = Field(..., alias="displayName")
    account_id: str
    properties: list[GaProperty] = Field(default_factory=list)

class AuditReport(BaseModel):
    gtm_accounts: list[GtmAccount]
    ga_accounts: list[GaAccount]

# --- Configuration Loading ---

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

# --- Authentication ---

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

# --- GTM Data Fetching ---

def fetch_gtm_accounts(service) -> list[dict[str, Any]]:
    return service.accounts().list().execute().get("account", [])

def fetch_gtm_containers(service, account_path: str) -> list[dict[str, Any]]:
    return service.accounts().containers().list(parent=account_path).execute().get("container", [])

def fetch_gtm_tags(service, container_path: str) -> list[dict[str, Any]]:
    workspace_path = f"{container_path}/workspaces/{DEFAULT_WORKSPACE_ID}"
    return service.accounts().containers().workspaces().tags().list(parent=workspace_path).execute().get("tag", [])

def build_gtm_accounts(service) -> list[GtmAccount]:
    accounts_list = []
    for acc in fetch_gtm_accounts(service):
        account_model = GtmAccount.model_validate(acc)
        containers = fetch_gtm_containers(service, acc["path"])
        for cont in containers:
            container_model = GtmContainer.model_validate(cont)
            tags = fetch_gtm_tags(service, cont["path"])
            container_model.tags = [GtmTag.model_validate(t) for t in tags]
            account_model.containers.append(container_model)
        accounts_list.append(account_model)
    return accounts_list

# --- GA4 Data Fetching ---

def fetch_ga_accounts(service) -> list[dict[str, Any]]:
    return service.accounts().list().execute().get("accounts", [])

def fetch_ga_properties(service, account_name: str) -> list[dict[str, Any]]:
    return service.properties().list(filter=f"parent:{account_name}").execute().get("properties", [])

def fetch_ga_data_streams(service, property_name: str) -> list[dict[str, Any]]:
    return service.properties().dataStreams().list(parent=property_name).execute().get("dataStreams", [])

def build_ga_accounts(service) -> list[GaAccount]:
    accounts_list = []
    for acc in fetch_ga_accounts(service):
        account_id = acc["name"].split("/")[1]
        account_model = GaAccount(display_name=acc["displayName"], account_id=account_id)
        properties = fetch_ga_properties(service, acc["name"])
        for prop in properties:
            prop_id = prop["name"].split("/")[1]
            streams_raw = fetch_ga_data_streams(service, prop["name"])
            streams_list = []
            for stream in streams_raw:
                stream_type = stream["type"].replace("_DATA_STREAM", "")
                measurement_id = None
                if stream_type == "WEB":
                    measurement_id = stream.get("webStreamData", {}).get("measurementId")
                streams_list.append(GaDataStream(
                    display_name=stream["displayName"],
                    type=stream_type,
                    measurement_id=measurement_id
                ))
            account_model.properties.append(GaProperty(
                property_id=prop_id,
                data_streams=streams_list,
                **prop
            ))
        accounts_list.append(account_model)
    return accounts_list

# --- Report Presentation ---

def print_text_report(report: AuditReport):
    print("\n--- Google Tag Manager ---")
    for account in report.gtm_accounts:
        print(f"\n[GTM Account] {account.name} (ID: {account.account_id})")
        for container in account.containers:
            print(f"  - [Container] {container.name} (Public ID: {container.public_id})")
            ga4_tags = [
                p["value"]
                for tag in container.tags
                if tag.type == "googtag" and tag.parameters
                for p in tag.parameters
                if p.get("key") == "measurementId"
            ]
            if ga4_tags:
                for mid in set(ga4_tags):
                    print(f"    - Links to GA4 Measurement ID: {mid}")
            else:
                print("    - No GA4 Configuration Tags found.")

    print("\n" + "=" * 40 + "\n")
    print("--- Google Analytics (GA4) ---")
    for account in report.ga_accounts:
        print(f"\n[GA Account] {account.display_name} (ID: {account.account_id})")
        for prop in account.properties:
            print(f"  - [Property] {prop.display_name} (ID: {prop.property_id})")
            print(f"    (Timezone: {prop.time_zone}, Currency: {prop.currency_code})")
            for stream in prop.data_streams:
                if stream.measurement_id:
                    print(f"    - [Stream] {stream.display_name} ({stream.type}) - ID: {stream.measurement_id}")

# --- Main Execution ---

def main():
    parser = argparse.ArgumentParser(description="Audit Google Marketing Platform configurations.")
    parser.add_argument("--json", action="store_true", help="Output the report in JSON format.")
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
            print(report.model_dump_json(indent=2, by_alias=True))
        else:
            print_text_report(report)

    except HttpError as e:
        print(f"An API HTTP error occurred: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
from typing import Any
from models import GtmAccount, GtmContainer, GtmTag, GaAccount, GaProperty, GaDataStream

# --- GTM Data Fetching ---


def _fetch_gtm_accounts(service) -> list[dict[str, Any]]:
    return service.accounts().list().execute().get("account", [])


def _fetch_gtm_containers(service, account_path: str) -> list[dict[str, Any]]:
    return (
        service.accounts()
        .containers()
        .list(parent=account_path)
        .execute()
        .get("container", [])
    )


def _fetch_live_gtm_tags(service, container_path: str) -> list[dict[str, Any]]:
    """Fetches tags from the live version of a container."""
    live_version = (
        service.accounts().containers().versions().live(parent=container_path).execute()
    )
    return live_version.get("tag", [])


def build_gtm_accounts(service) -> list[GtmAccount]:
    accounts_list: list[GtmAccount] = []
    for acc in _fetch_gtm_accounts(service):
        account_model = GtmAccount.model_validate(acc)
        containers = _fetch_gtm_containers(service, acc["path"])
        for cont in containers:
            container_model = GtmContainer.model_validate(cont)
            tags = _fetch_live_gtm_tags(service, cont["path"])
            container_model.tags = [GtmTag.model_validate(t) for t in tags]
            account_model.containers.append(container_model)
        accounts_list.append(account_model)
    return accounts_list


# --- GA4 Data Fetching ---


def _fetch_ga_accounts(service) -> list[dict[str, Any]]:
    return service.accounts().list().execute().get("accounts", [])


def _fetch_ga_properties(service, account_name: str) -> list[dict[str, Any]]:
    return (
        service.properties()
        .list(filter=f"parent:{account_name}")
        .execute()
        .get("properties", [])
    )


def _fetch_ga_data_streams(service, property_name: str) -> list[dict[str, Any]]:
    return (
        service.properties()
        .dataStreams()
        .list(parent=property_name)
        .execute()
        .get("dataStreams", [])
    )


def build_ga_accounts(service) -> list[GaAccount]:
    accounts_list: list[GaAccount] = []
    for acc in _fetch_ga_accounts(service):
        account_id = acc["name"].split("/")[1]
        account_model = GaAccount(
            display_name=acc["displayName"], account_id=account_id
        )

        properties = _fetch_ga_properties(service, acc["name"])
        for prop in properties:
            prop_id = prop["name"].split("/")[1]

            streams_raw = _fetch_ga_data_streams(service, prop["name"])
            streams_list: list[GaDataStream] = []
            for stream in streams_raw:
                stream_type = stream["type"].replace("_DATA_STREAM", "")
                measurement_id = None
                if stream_type == "WEB":
                    measurement_id = stream.get("webStreamData", {}).get(
                        "measurementId"
                    )
                elif stream_type == "IOS_APP":
                    measurement_id = stream.get("iosAppStreamData", {}).get(
                        "firebaseAppId"
                    )
                elif stream_type == "ANDROID_APP":
                    measurement_id = stream.get("androidAppStreamData", {}).get(
                        "firebaseAppId"
                    )

                streams_list.append(
                    GaDataStream(
                        display_name=stream["displayName"],
                        type=stream_type,
                        measurement_id=measurement_id,
                    )
                )

            account_model.properties.append(
                GaProperty(
                    property_id=prop_id,
                    data_streams=streams_list,
                    **prop,
                )
            )
        accounts_list.append(account_model)
    return accounts_list

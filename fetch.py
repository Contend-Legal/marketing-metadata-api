from typing import Any, Callable, Optional
from googleapiclient.errors import HttpError
import json
from models import (
    GtmAccount,
    GtmContainer,
    GtmTag,
    GtmTrigger,
    GtmVariable,
    GaAccount,
    GaProperty,
    GaDataStream,
)

# Type alias for the logger function
LogFunc = Callable[[str], None]


def _noop_log(msg: str) -> None:
    pass


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


def _fetch_live_version(service, container_path: str) -> Optional[dict[str, Any]]:
    """Fetches the live version of a container. Returns None if no live version exists."""
    try:
        return (
            service.accounts()
            .containers()
            .versions()
            .live(parent=container_path)
            .execute()
        )
    except HttpError as e:
        if e.resp.status == 404:
            return None
        raise


def build_gtm_accounts(service, log: LogFunc = _noop_log) -> list[GtmAccount]:
    accounts_list: list[GtmAccount] = []
    for acc in _fetch_gtm_accounts(service):
        log(f"  Processing GTM account: {acc['name']}")
        account_model = GtmAccount.model_validate(acc)
        containers = _fetch_gtm_containers(service, acc["path"])

        for cont in containers:
            log(f"    Processing container: {cont['name']}")
            container_model = GtmContainer.model_validate(cont)

            live_version = _fetch_live_version(service, cont["path"])
            if live_version is None:
                container_model.error = "No live version published"
                log(f"      Warning: No live version for {cont['name']}")
            else:
                container_model.live_version_id = live_version.get("containerVersionId")

                KEYS_TO_EXPAND = [
                    "tag",
                    "parameter",
                    "firingTriggerId",
                    "monitoringMetadata",
                    "consentSettings",
                ]

                # Log a summary of the live version structure, showing all fields but truncating long values
                def truncate_string(
                    val, truncate_at: int = 100, truncate_to: int = 20
                ) -> Any:
                    if isinstance(val, str) and len(val) > truncate_at:
                        return val[:truncate_to] + "…"
                    return val

                def summarize_object(
                    obj: Any,
                    max_depth: int | None = None,
                    current_depth: int = 0,
                    parent_key: str = "",
                ) -> Any:
                    if parent_key in KEYS_TO_EXPAND:
                        max_depth = None  # Expand fully

                    if max_depth is not None and current_depth >= max_depth:
                        if hasattr(obj, "name"):
                            return f"<{obj.name} ...>"
                        return f"{str(type(obj))}"

                    if isinstance(obj, dict):
                        summary = {}
                        for k, v in obj.items():
                            if isinstance(v, str):
                                summary[k] = truncate_string(v)
                            elif isinstance(v, list):
                                summary[k] = [
                                    summarize_object(
                                        item,
                                        max_depth=max_depth,
                                        current_depth=current_depth + 1,
                                        parent_key=k,
                                    )
                                    for item in v
                                ]
                            elif isinstance(v, dict):
                                summary[k] = summarize_object(
                                    v,
                                    max_depth=max_depth,
                                    current_depth=current_depth + 1,
                                    parent_key=k,
                                )
                            else:
                                summary[k] = v
                        return summary
                    elif isinstance(obj, list):
                        return [
                            summarize_object(
                                item,
                                max_depth=max_depth,
                                current_depth=current_depth + 1,
                                parent_key=parent_key,
                            )
                            for item in obj
                        ]
                    return obj

                summary = summarize_object(live_version, max_depth=1)
                log("      LIVE VERSION SUMMARY:")
                log(json.dumps(summary, indent=2, ensure_ascii=False))

                container_model.tags = [
                    GtmTag.model_validate(t) for t in live_version.get("tag", [])
                ]
                container_model.triggers = [
                    GtmTrigger.model_validate(t)
                    for t in live_version.get("trigger", [])
                ]
                container_model.variables = [
                    GtmVariable.model_validate(v)
                    for v in live_version.get("variable", [])
                ]
                log(
                    f"      Found {len(container_model.tags)} tags, "
                    f"{len(container_model.triggers)} triggers, "
                    f"{len(container_model.variables)} variables"
                )

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


def build_ga_accounts(service, log: LogFunc = _noop_log) -> list[GaAccount]:
    accounts_list: list[GaAccount] = []
    for acc in _fetch_ga_accounts(service):
        log(f"  Processing GA account: {acc['displayName']}")
        account_id = acc["name"].split("/")[1]
        account_model = GaAccount(
            display_name=acc["displayName"], account_id=account_id
        )

        properties = _fetch_ga_properties(service, acc["name"])
        for prop in properties:
            log(f"    Processing property: {prop['displayName']}")
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
            log(f"      Found {len(streams_list)} data streams")

            account_model.properties.append(
                GaProperty(
                    property_id=prop_id,
                    data_streams=streams_list,
                    **prop,
                )
            )
        accounts_list.append(account_model)
    return accounts_list

from pathlib import Path
from datetime import datetime
from models import AuditReport


def get_output_filepath(directory: str, extension: str) -> Path:
    """Generate a timestamped output file path."""
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_dir / f"audit_{timestamp}.{extension}"


def format_json_report(report: AuditReport) -> str:
    """Returns the report as a JSON string."""
    return report.model_dump_json(indent=2, by_alias=True)


def format_text_report(report: AuditReport) -> str:
    """Returns a human-readable report string."""
    lines: list[str] = []

    lines.append("\n" + "=" * 50)
    lines.append("GOOGLE TAG MANAGER")
    lines.append("=" * 50)

    for account in report.gtm_accounts:
        lines.append(f"\n[Account] {account.name} (ID: {account.account_id})")
        for container in account.containers:
            lines.append(f"  [Container] {container.name} (ID: {container.public_id})")
            if container.error:
                lines.append(f"    ⚠ {container.error}")
                continue

            lines.append(f"    Live Version: {container.live_version_id}")

            # Show GA4 links
            ga4_ids = _extract_ga4_measurement_ids(container)
            if ga4_ids:
                for mid in ga4_ids:
                    lines.append(f"    → Links to GA4: {mid}")

            # Show tag summary by type
            tag_types: dict[str, int] = {}
            for tag in container.tags:
                tag_types[tag.type] = tag_types.get(tag.type, 0) + 1
            lines.append(f"    Tags ({len(container.tags)}):")
            for tag_type, count in sorted(tag_types.items()):
                lines.append(f"      - {tag_type}: {count}")

            lines.append(f"    Triggers: {len(container.triggers)}")
            lines.append(f"    Variables: {len(container.variables)}")

    lines.append("\n" + "=" * 50)
    lines.append("GOOGLE ANALYTICS 4")
    lines.append("=" * 50)

    for account in report.ga_accounts:
        lines.append(f"\n[Account] {account.display_name} (ID: {account.account_id})")
        for prop in account.properties:
            lines.append(f"  [Property] {prop.display_name} (ID: {prop.property_id})")
            lines.append(
                f"    Timezone: {prop.time_zone} | Currency: {prop.currency_code}"
            )
            for stream in prop.data_streams:
                if stream.measurement_id:
                    lines.append(
                        f"    [Stream] {stream.display_name} → {stream.measurement_id}"
                    )

    # Summary
    s = report.summary
    lines.append("\n" + "=" * 50)
    lines.append("SUMMARY")
    lines.append("=" * 50)
    lines.append(
        f"GTM: {s.gtm_accounts} accounts, {s.gtm_containers} containers, "
        f"{s.gtm_tags} tags, {s.gtm_triggers} triggers, {s.gtm_variables} variables"
    )
    lines.append(
        f"GA4: {s.ga_accounts} accounts, {s.ga_properties} properties, "
        f"{s.ga_streams} data streams"
    )
    lines.append("")

    return "\n".join(lines)


def _extract_ga4_measurement_ids(container) -> set[str]:
    """Extract GA4 measurement IDs from a container's tags."""
    ids: set[str] = set()
    for tag in container.tags:
        if tag.type == "googtag" and tag.parameters:
            for p in tag.parameters:
                if p.get("key") == "measurementId":
                    ids.add(p.get("value", ""))
    return ids


def print_json_report(report: AuditReport) -> None:
    print(format_json_report(report))


def print_text_report(report: AuditReport) -> None:
    print(format_text_report(report))


def save_report(report: AuditReport, directory: str, as_json: bool) -> Path:
    """Save the report to a file and return the path."""
    if as_json:
        filepath = get_output_filepath(directory, "json")
        content = format_json_report(report)
    else:
        filepath = get_output_filepath(directory, "txt")
        content = format_text_report(report)

    filepath.write_text(content)
    return filepath

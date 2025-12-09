from models import AuditReport


def print_json_report(report: AuditReport):
    """Prints the report in JSON format."""
    print(report.model_dump_json(indent=2, by_alias=True))


def print_text_report(report: AuditReport):
    """Prints a human-readable report to the console."""
    print("\n--- Google Tag Manager ---")
    for account in report.gtm_accounts:
        print(f"\n[GTM Account] {account.name} (ID: {account.account_id})")
        for container in account.containers:
            print(
                f"  - [Container] {container.name} (Public ID: {container.public_id})"
            )
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
                print("    - No GA4 Configuration Tags found in Live version.")

    print("\n" + "=" * 40 + "\n")
    print("--- Google Analytics (GA4) ---")
    for account in report.ga_accounts:
        print(f"\n[GA Account] {account.display_name} (ID: {account.account_id})")
        for prop in account.properties:
            print(f"  - [Property] {prop.display_name} (ID: {prop.property_id})")
            print(f"    (Timezone: {prop.time_zone}, Currency: {prop.currency_code})")
            for stream in prop.data_streams:
                if stream.measurement_id:
                    print(
                        f"    - [Stream] {stream.display_name} ({stream.type}) - ID: {stream.measurement_id}"
                    )

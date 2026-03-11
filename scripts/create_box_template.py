#!/usr/bin/env python3
"""
Create Box metadata template for GeoBox Intelligence

This script creates the 'geoBoxIntelligence' metadata template in Box
that stores GPS coordinates and validation results.

Uses box_sdk_gen (Box SDK v10+) to match the main application.

IMPORTANT: Box automatically removes underscores from field keys,
so all keys here use no underscores (e.g. 'gpstimestamp' not 'gps_timestamp').
"""

from box_sdk_gen import BoxClient, BoxJWTAuth, JWTConfig
import json
import sys


def create_metadata_template():
    """Create the GeoBox Intelligence metadata template in Box"""

    # Load Box config
    try:
        with open('config/box_config.json', 'r') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("Error: config/box_config.json not found!")
        print("Please ensure your Box JWT config is in config/box_config.json")
        sys.exit(1)

    # Authenticate with Box (box_sdk_gen v10+)
    print("Authenticating with Box...")
    jwt_config = JWTConfig.from_config_json_string(json.dumps(config))
    auth = BoxJWTAuth(config=jwt_config)
    client = BoxClient(auth=auth)

    # Get current user info
    user = client.users.get_user_me()
    print(f"Authenticated as: {user.name}")

    # Define metadata template
    # NOTE: Box removes underscores from field keys automatically.
    # Use keys without underscores to match what Box actually stores.
    template_key = "geoBoxIntelligence"
    display_name = "GeoBox Intelligence"

    fields = [
        {
            "type": "float",
            "key": "latitude",
            "displayName": "Latitude",
            "description": "GPS Latitude coordinate"
        },
        {
            "type": "float",
            "key": "longitude",
            "displayName": "Longitude",
            "description": "GPS Longitude coordinate"
        },
        {
            "type": "float",
            "key": "altitude",
            "displayName": "Altitude (meters)",
            "description": "GPS Altitude in meters"
        },
        {
            "type": "string",
            "key": "gpstimestamp",
            "displayName": "GPS Timestamp",
            "description": "Timestamp when GPS coordinates were captured"
        },
        {
            "type": "multiSelect",
            "key": "validationstatus",
            "displayName": "Validation Status",
            "description": "GPS validation result",
            "options": [
                {"key": "valid"},
                {"key": "flagged"},
                {"key": "no_gps"},
                {"key": "error"}
            ]
        },
        {
            "type": "float",
            "key": "confidence",
            "displayName": "Confidence Score",
            "description": "AI validation confidence (0.0 to 1.0)"
        },
        {
            "type": "string",
            "key": "ainotes",
            "displayName": "AI Notes",
            "description": "AI validation notes and insights"
        },
        {
            "type": "string",
            "key": "processingdate",
            "displayName": "Processing Date",
            "description": "When GeoBox processed this file"
        }
    ]

    # Check if template already exists
    print(f"\nChecking if template '{template_key}' exists...")

    try:
        templates = client.metadata_templates.get_enterprise_metadata_templates()
        template_exists = any(
            t.template_key == template_key
            for t in templates.entries
        )

        if template_exists:
            print(f"Template '{template_key}' already exists! Skipping creation.")
            return True

    except Exception as e:
        print(f"Could not check existing templates: {e}")
        print("Proceeding with creation...")

    # Create the template
    print(f"\nCreating metadata template: {display_name}...")

    try:
        template = client.metadata_templates.create_metadata_template(
            scope="enterprise",
            template_key=template_key,
            display_name=display_name,
            hidden=False,
            fields=fields,
        )

        print(f"Metadata template created successfully!")
        print(f"\nTemplate Details:")
        print(f"   Template Key: {template.template_key}")
        print(f"   Display Name: {template.display_name}")
        print(f"   Scope: {template.scope}")
        print(f"   Fields: {len(template.fields)}")

        print(f"\nFields:")
        for field in template.fields:
            print(f"   - {field.display_name} ({field.type})")

        return True

    except Exception as e:
        error_str = str(e)
        print(f"Error creating template: {error_str}")

        if "already exists" in error_str.lower() or "conflict" in error_str.lower():
            print("Template already exists - this is OK!")
            return True

        return False


if __name__ == "__main__":
    print("=" * 60)
    print("GeoBox - Create Box Metadata Template")
    print("=" * 60)

    success = create_metadata_template()

    print("\n" + "=" * 60)
    if success:
        print("Setup Complete!")
        print("\nNext step: Upload a geotagged photo to Box and watch it process!")
    else:
        print("Setup Failed!")
        print("\nPlease check the error messages above and try again.")
    print("=" * 60)

    sys.exit(0 if success else 1)

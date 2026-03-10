"""
transpiler/metadata_updater.py — Script to refresh api_metadata.json from Roblox API.
"""

import json
import os
import requests

API_DUMP_URL = "https://raw.githubusercontent.com/MaximumADHD/Roblox-Client-Tracker/roblox/API-Dump.json"

# Globals that aren't usually in the reflection dump but required for RPy
FIXED_GLOBALS = {
    "game": "DataModel",
    "workspace": "Workspace",
    "Instance": "Instance",
    "Vector3": "Vector3",
    "CFrame": "CFrame",
    "Color3": "Color3"
}

# Methods we know are 'dot' style
DOT_METHODS = {
    "Instance": {"new"},
    "Vector3": {"new"},
    "CFrame": {"new"},
    "Color3": {"new", "fromRGB", "fromHSV"}
}

def is_deprecated(tags):
    if not tags: return False
    return "Deprecated" in tags or "Hidden" in tags or "NotBrowsable" in tags

def get_type_name(t_info):
    if not t_info:
        return "any"
    if isinstance(t_info, list):
        if not t_info: return "any"
        # Take the first return type if multiple
        return get_type_name(t_info[0])
    if isinstance(t_info, dict):
        return t_info.get("Name", "any")
    return "any"

def update_metadata():
    print(f"Fetching API Dump from {API_DUMP_URL}...")
    try:
        response = requests.get(API_DUMP_URL)
        response.raise_for_status()
        dump = response.json()
    except Exception as e:
        print(f"Error fetching API dump: {e}")
        return

    metadata = {
        "classes": {},
        "globals": FIXED_GLOBALS
    }

    for r_class in dump.get("Classes", []):
        class_name = r_class["Name"]
        
        # Skip if deprecated
        if is_deprecated(r_class.get("Tags")):
            continue

        class_info = {
            "inherits": r_class.get("Superclass"),
            "properties": {},
            "methods": {},
            "signals": {}
        }

        for member in r_class.get("Members", []):
            m_type = member["MemberType"]
            m_name = member["Name"]
            
            if is_deprecated(member.get("Tags")):
                continue

            if m_type == "Property":
                v_type = get_type_name(member.get("ValueType"))
                class_info["properties"][m_name] = v_type
            
            elif m_type == "Function":
                r_type = get_type_name(member.get("ReturnType"))
                style = "dot" if m_name in DOT_METHODS.get(class_name, set()) else "colon"
                class_info["methods"][m_name] = {
                    "returns": r_type,
                    "style": style
                }
            
            elif m_type == "Event":
                class_info["signals"][m_name] = "RBXScriptSignal"

        # Cleanup empty categories
        for cat in ["properties", "methods", "signals"]:
            if not class_info[cat]:
                del class_info[cat]

        metadata["classes"][class_name] = class_info

    output_path = os.path.join(os.path.dirname(__file__), "api_metadata.json")
    with open(output_path, "w") as f:
        json.dump(metadata, f, indent=2)
    
    print(f"Successfully updated {output_path}")
    print(f"Indexed {len(metadata['classes'])} classes.")

if __name__ == "__main__":
    update_metadata()

#!/usr/bin/env python3
"""Verify that generated default assets contain the configured MultiNet command."""

import argparse
import json
import struct
from pathlib import Path

if __package__:
    from .build_default_assets import read_custom_wake_word_from_sdkconfig
else:
    from build_default_assets import read_custom_wake_word_from_sdkconfig


ASSET_HEADER_SIZE = 12
ASSET_ENTRY_SIZE = 44


def read_asset_files(assets_path):
    """Read files from the esp_mmap_assets binary format."""
    data = Path(assets_path).read_bytes()
    if len(data) < ASSET_HEADER_SIZE:
        raise ValueError("Assets binary is shorter than its header")

    file_count, checksum, data_length = struct.unpack_from("<III", data)
    if data_length != len(data) - ASSET_HEADER_SIZE:
        raise ValueError("Assets binary length does not match its header")
    if sum(data[ASSET_HEADER_SIZE:]) & 0xFFFF != checksum:
        raise ValueError("Assets binary checksum mismatch")

    table_end = ASSET_HEADER_SIZE + file_count * ASSET_ENTRY_SIZE
    if table_end > len(data):
        raise ValueError("Assets file table is truncated")

    payload = data[table_end:]
    files = {}
    for index in range(file_count):
        entry_offset = ASSET_HEADER_SIZE + index * ASSET_ENTRY_SIZE
        name = data[entry_offset:entry_offset + 32].split(b"\0", 1)[0].decode("utf-8")
        file_size, file_offset = struct.unpack_from("<II", data, entry_offset + 32)
        content_offset = file_offset + 2
        content_end = content_offset + file_size
        if content_offset < 2 or content_end > len(payload):
            raise ValueError(f"Asset entry {name!r} is outside the payload")
        files[name] = payload[content_offset:content_end]

    return files


def verify_default_assets(sdkconfig_path, assets_path):
    """Raise ValueError unless the packaged command exactly matches sdkconfig."""
    expected = read_custom_wake_word_from_sdkconfig(sdkconfig_path)
    if expected is None:
        raise ValueError("Custom wake word is not fully configured in sdkconfig")

    files = read_asset_files(assets_path)
    try:
        index = json.loads(files["index.json"].decode("utf-8"))
    except KeyError as error:
        raise ValueError("Assets binary does not contain index.json") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Assets index.json is invalid") from error

    multinet = index.get("multinet_model")
    if not isinstance(multinet, dict):
        raise ValueError("Assets index.json does not contain MultiNet metadata")

    commands = multinet.get("commands")
    expected_command = {
        "command": expected["wake_word"],
        "text": expected["display"],
        "action": "wake",
    }
    if commands != [expected_command]:
        raise ValueError(
            f"Packaged MultiNet commands {commands!r} do not match sdkconfig "
            f"command {[expected_command]!r}"
        )

    return expected_command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sdkconfig", required=True, help="Effective sdkconfig file")
    parser.add_argument("--assets", required=True, help="Generated assets.bin file")
    args = parser.parse_args()

    command = verify_default_assets(args.sdkconfig, args.assets)
    print(
        "Verified packaged MultiNet wake command: "
        f"{command['command']} ({command['text']})"
    )


if __name__ == "__main__":
    main()

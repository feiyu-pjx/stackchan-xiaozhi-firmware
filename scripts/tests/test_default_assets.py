import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from scripts.build_default_assets import (
    build_assets_integrated,
    build_multinet_model_info,
    generate_index_json,
    pack_assets_simple,
    read_custom_wake_word_from_sdkconfig,
)
from scripts.verify_default_assets import read_asset_files, verify_default_assets


class DefaultAssetsWakeWordTest(unittest.TestCase):
    def test_packed_command_comes_from_sdkconfig_and_keeps_display_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sdkconfig = root / "sdkconfig"
            sdkconfig.write_text(
                'CONFIG_USE_CUSTOM_WAKE_WORD=y\n'
                'CONFIG_CUSTOM_WAKE_WORD="turn on the lantern"\n'
                'CONFIG_CUSTOM_WAKE_WORD_DISPLAY="点亮灯笼"\n'
                'CONFIG_WAKE_WORD_SENSITIVITY_HIGH=y\n',
                encoding="utf-8",
            )
            config = read_custom_wake_word_from_sdkconfig(str(sdkconfig))
            model_info = build_multinet_model_info(config, ["mn6_cn"])
            assets_dir = root / "assets"
            assets_dir.mkdir()
            generate_index_json(str(assets_dir), "srmodels.bin", None, None,
                                multinet_model_info=model_info)
            (assets_dir / "srmodels.bin").write_bytes(b"test model")
            output_path = root / "generated_assets.bin"

            pack_assets_simple(
                str(assets_dir), str(root / "include"), str(output_path), "assets"
            )

            self.assertEqual(
                verify_default_assets(str(sdkconfig), str(output_path)),
                {
                    "command": "turn on the lantern",
                    "text": "点亮灯笼",
                    "action": "wake",
                },
            )

    def test_rejects_stale_packaged_command(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sdkconfig = root / "sdkconfig"
            sdkconfig.write_text(
                'CONFIG_USE_CUSTOM_WAKE_WORD=y\n'
                'CONFIG_CUSTOM_WAKE_WORD="da fei yu"\n'
                'CONFIG_CUSTOM_WAKE_WORD_DISPLAY="大肥鱼"\n'
                'CONFIG_WAKE_WORD_SENSITIVITY_HIGH=y\n',
                encoding="utf-8",
            )
            assets_dir = root / "assets"
            assets_dir.mkdir()
            (assets_dir / "index.json").write_text(
                json.dumps({
                    "multinet_model": {
                        "commands": [{
                            "command": "ni hao xiao zhi",
                            "text": "你好小智",
                            "action": "wake",
                        }]
                    }
                }),
                encoding="utf-8",
            )
            output_path = root / "generated_assets.bin"
            pack_assets_simple(
                str(assets_dir), str(root / "include"), str(output_path), "assets"
            )

            with self.assertRaisesRegex(ValueError, "do not match sdkconfig"):
                verify_default_assets(str(sdkconfig), str(output_path))

    def test_generated_assets_include_full_face_emotes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            emoji_dir = root / "emojis"
            emoji_dir.mkdir()
            (emoji_dir / "happy.png").write_bytes(b"previous happy asset")
            output_path = root / "generated_assets.bin"

            self.assertTrue(
                build_assets_integrated(
                    [], [], None, str(emoji_dir), None, str(output_path),
                    full_face_emotes=True,
                )
            )
            packaged_files = read_asset_files(output_path)
            index = json.loads(packaged_files["index.json"].decode("utf-8"))
            packaged_emotions = {
                entry["name"]: entry["file"] for entry in index["emoji_collection"]
            }
            emotion_names = {
                "neutral", "happy", "sad", "angry", "surprised",
                "thinking", "sleepy", "listening", "speaking",
            }

            self.assertEqual(set(packaged_emotions), emotion_names)
            self.assertEqual(len(index["emoji_collection"]), len(emotion_names))
            for filename in set(packaged_emotions.values()):
                image = packaged_files[filename]
                self.assertEqual(image[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(image[24:29], b"\x08\x06\x00\x00\x00")
                width, height = struct.unpack_from(">II", image, 16)
                offset = 8
                image_data = bytearray()
                while offset < len(image):
                    chunk_size = struct.unpack_from(">I", image, offset)[0]
                    chunk_type = image[offset + 4:offset + 8]
                    chunk_data = image[offset + 8:offset + 8 + chunk_size]
                    chunk_crc = struct.unpack_from(">I", image, offset + 8 + chunk_size)[0]
                    self.assertEqual(
                        chunk_crc, zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
                    )
                    if chunk_type == b"IDAT":
                        image_data.extend(chunk_data)
                    offset += chunk_size + 12
                    if chunk_type == b"IEND":
                        break
                self.assertEqual(len(zlib.decompress(image_data)), height * (width * 4 + 1))


if __name__ == "__main__":
    unittest.main()

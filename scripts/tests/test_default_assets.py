import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_default_assets import (
    build_multinet_model_info,
    generate_index_json,
    pack_assets_simple,
    read_custom_wake_word_from_sdkconfig,
)
from scripts.verify_default_assets import verify_default_assets


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


if __name__ == "__main__":
    unittest.main()

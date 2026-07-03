import tempfile
import unittest
from pathlib import Path

from twitter_research.config import load_config


class ConfigTests(unittest.TestCase):
    def test_loads_optional_xai_api_key_without_model_setting(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "XAI_API_KEY=xai-token\n"
                "XAI_MODEL=grok-test-model\n",
                encoding="utf-8",
            )

            config = load_config(env_path=env_path, environ={})

            self.assertEqual(config.xai_api_key, "xai-token")
            self.assertFalse(hasattr(config, "xai_model"))

    def test_environment_variable_overrides_env_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("XAI_API_KEY=file-token\n", encoding="utf-8")

            config = load_config(
                env_path=env_path,
                environ={"XAI_API_KEY": "shell-token"},
            )

            self.assertEqual(config.xai_api_key, "shell-token")

    def test_loads_optional_socialdata_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("SOCIALDATA_API_KEY=socialdata-token\n", encoding="utf-8")

            config = load_config(env_path=env_path, environ={})

            self.assertEqual(config.socialdata_api_key, "socialdata-token")

    def test_loads_optional_nansen_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("NANSEN_API_KEY=nansen-token\n", encoding="utf-8")

            config = load_config(env_path=env_path, environ={})

            self.assertEqual(config.nansen_api_key, "nansen-token")

    def test_loads_optional_surf_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text("SURF_API_KEY=surf-token\n", encoding="utf-8")

            config = load_config(env_path=env_path, environ={})

            self.assertEqual(config.surf_api_key, "surf-token")

    def test_missing_env_file_returns_empty_config(self):
        config = load_config(env_path=Path("/missing/.env"), environ={})

        self.assertIsNone(config.xai_api_key)
        self.assertIsNone(config.socialdata_api_key)
        self.assertIsNone(config.nansen_api_key)
        self.assertIsNone(config.surf_api_key)


if __name__ == "__main__":
    unittest.main()

import os
import unittest
from core.config import Settings

class TestObservabilityIntegration(unittest.TestCase):
    def setUp(self):
        # Save original env
        self.original_keys = [
            "LANGSMITH_TRACING",
            "LANGCHAIN_TRACING_V2",
            "LANGSMITH_API_KEY",
            "LANGCHAIN_API_KEY",
            "LANGSMITH_PROJECT",
            "LANGCHAIN_PROJECT",
            "LANGSMITH_ENDPOINT",
            "LANGCHAIN_ENDPOINT",
        ]
        self.original_env = {k: os.environ.get(k) for k in self.original_keys}
        # Clean up env for test
        for k in self.original_env:
            if k in os.environ:
                del os.environ[k]

    def tearDown(self):
        # Restore env
        for k, v in self.original_env.items():
            if v is None:
                if k in os.environ:
                    del os.environ[k]
            else:
                os.environ[k] = v

    def test_settings_default_values(self):
        settings = Settings(_env_file=None)
        self.assertFalse(settings.LANGSMITH_TRACING)
        self.assertFalse(settings.LANGCHAIN_TRACING_V2)
        self.assertIsNone(settings.LANGSMITH_API_KEY)
        self.assertIsNone(settings.LANGCHAIN_API_KEY)
        self.assertEqual(settings.LANGSMITH_PROJECT, "aiagent")
        self.assertEqual(settings.LANGCHAIN_PROJECT, "aiagent")
        self.assertEqual(settings.LANGSMITH_ENDPOINT, "https://api.smith.langchain.com")

    def test_export_to_env_enabled(self):
        settings = Settings(
            LANGSMITH_TRACING=True,
            LANGSMITH_API_KEY="test-key-12345",
            LANGSMITH_PROJECT="aiagent",
            LANGSMITH_ENDPOINT="https://api.smith.langchain.com"
        )
        settings.export_to_env()
        
        self.assertEqual(os.environ.get("LANGSMITH_TRACING"), "true")
        self.assertEqual(os.environ.get("LANGCHAIN_TRACING_V2"), "true")
        self.assertEqual(os.environ.get("LANGSMITH_API_KEY"), "test-key-12345")
        self.assertEqual(os.environ.get("LANGCHAIN_API_KEY"), "test-key-12345")
        self.assertEqual(os.environ.get("LANGSMITH_PROJECT"), "aiagent")
        self.assertEqual(os.environ.get("LANGCHAIN_PROJECT"), "aiagent")
        self.assertEqual(os.environ.get("LANGSMITH_ENDPOINT"), "https://api.smith.langchain.com")

    def test_export_to_env_disabled(self):
        settings = Settings(
            LANGSMITH_TRACING=False,
            LANGCHAIN_TRACING_V2=False,
            LANGSMITH_API_KEY=None,
            LANGCHAIN_API_KEY=None,
        )
        settings.export_to_env()
        
        # Should NOT be in os.environ because tracing is disabled
        self.assertNotIn("LANGSMITH_TRACING", os.environ)
        self.assertNotIn("LANGCHAIN_TRACING_V2", os.environ)


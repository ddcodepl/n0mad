#!/usr/bin/env python3
"""
Integration tests for configuration management with main application.
"""

import os
import unittest
from unittest.mock import patch

from src.config import config_manager


class TestConfigurationIntegration(unittest.TestCase):
    """Integration tests for configuration management."""

    def test_global_config_manager_instance(self):
        """Test that global config manager instance works correctly."""
        # Test default values
        self.assertFalse(config_manager.get_enable_continuous_polling())
        self.assertEqual(config_manager.get_polling_interval_minutes(), 1)

        # Test modification
        config_manager.set_enable_continuous_polling(True)
        config_manager.set_polling_interval_minutes(5)

        self.assertTrue(config_manager.get_enable_continuous_polling())
        self.assertEqual(config_manager.get_polling_interval_minutes(), 5)

        # Reset to defaults for other tests
        config_manager.set_enable_continuous_polling(False)
        config_manager.set_polling_interval_minutes(1)

    def test_continuous_polling_workflow_simulation(self):
        """Test simulated workflow with continuous polling enabled."""
        # Simulate enabling continuous polling with 3-minute intervals
        config_manager.set_enable_continuous_polling(True)
        config_manager.set_polling_interval_minutes(3)

        # Verify configuration for workflow logic
        self.assertTrue(config_manager.get_enable_continuous_polling())
        self.assertEqual(config_manager.get_polling_interval_minutes(), 3)

        # Simulate getting configuration for polling loop
        config_dict = config_manager.get_all_config()

        # Check that workflow would use correct values
        if config_dict["enable_continuous_polling"]:
            polling_interval_seconds = config_dict["polling_interval_minutes"] * 60
            self.assertEqual(polling_interval_seconds, 180)  # 3 minutes = 180 seconds

        # Reset configuration
        config_manager.set_enable_continuous_polling(False)
        config_manager.set_polling_interval_minutes(1)

    @patch.dict(
        os.environ,
        {"ENABLE_CONTINUOUS_POLLING": "true", "POLLING_INTERVAL_MINUTES": "10"},
        clear=True,
    )
    def test_environment_configuration_scenario(self):
        """Test configuration loaded from environment for production deployment."""
        # Import and create new instance to test environment loading
        from src.config import ConfigurationManager

        env_config = ConfigurationManager()

        # Verify environment values were loaded
        self.assertTrue(env_config.get_enable_continuous_polling())
        self.assertEqual(env_config.get_polling_interval_minutes(), 10)

        # Test validation still works
        self.assertTrue(env_config.validate_config())


if __name__ == "__main__":
    unittest.main()

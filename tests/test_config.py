#!/usr/bin/env python3
"""
Unit tests for configuration management system.
"""

import os
import unittest
from unittest.mock import patch

from src.config import DEFAULT_ENABLE_CONTINUOUS_POLLING, DEFAULT_MODEL, DEFAULT_POLLING_INTERVAL_MINUTES, MIN_POLLING_INTERVAL_MINUTES, ConfigurationManager


class TestConfigurationManager(unittest.TestCase):
    """Test cases for ConfigurationManager class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.config_manager = ConfigurationManager()

    def test_default_values(self):
        """Test that default values are loaded correctly."""
        self.assertEqual(self.config_manager.get_model(), DEFAULT_MODEL)
        self.assertEqual(self.config_manager.get_enable_continuous_polling(), DEFAULT_ENABLE_CONTINUOUS_POLLING)
        self.assertEqual(self.config_manager.get_polling_interval_minutes(), DEFAULT_POLLING_INTERVAL_MINUTES)

    def test_model_getter_setter(self):
        """Test model getter and setter methods."""
        # Test setting valid model
        test_model = "test/model-v1"
        self.config_manager.set_model(test_model)
        self.assertEqual(self.config_manager.get_model(), test_model)

        # Test setting model with whitespace
        test_model_with_spaces = "  test/model-v2  "
        self.config_manager.set_model(test_model_with_spaces)
        self.assertEqual(self.config_manager.get_model(), test_model_with_spaces.strip())

    def test_model_validation(self):
        """Test model validation."""
        # Test empty string
        with self.assertRaises(ValueError):
            self.config_manager.set_model("")

        # Test whitespace-only string
        with self.assertRaises(ValueError):
            self.config_manager.set_model("   ")

        # Test non-string type
        with self.assertRaises(ValueError):
            self.config_manager.set_model(123)

        with self.assertRaises(ValueError):
            self.config_manager.set_model(None)

    def test_continuous_polling_getter_setter(self):
        """Test continuous polling getter and setter methods."""
        # Test setting to True
        self.config_manager.set_enable_continuous_polling(True)
        self.assertTrue(self.config_manager.get_enable_continuous_polling())

        # Test setting to False
        self.config_manager.set_enable_continuous_polling(False)
        self.assertFalse(self.config_manager.get_enable_continuous_polling())

    def test_continuous_polling_validation(self):
        """Test continuous polling validation."""
        # Test non-boolean types
        with self.assertRaises(ValueError):
            self.config_manager.set_enable_continuous_polling("true")

        with self.assertRaises(ValueError):
            self.config_manager.set_enable_continuous_polling(1)

        with self.assertRaises(ValueError):
            self.config_manager.set_enable_continuous_polling(None)

    def test_polling_interval_getter_setter(self):
        """Test polling interval getter and setter methods."""
        # Test setting valid intervals
        test_intervals = [1, 5, 60, 1440]  # 1 min, 5 min, 1 hour, 1 day
        for interval in test_intervals:
            self.config_manager.set_polling_interval_minutes(interval)
            self.assertEqual(self.config_manager.get_polling_interval_minutes(), interval)

    def test_polling_interval_validation(self):
        """Test polling interval validation."""
        # Test minimum value constraint
        with self.assertRaises(ValueError):
            self.config_manager.set_polling_interval_minutes(0)

        with self.assertRaises(ValueError):
            self.config_manager.set_polling_interval_minutes(-1)

        # Test non-integer types
        with self.assertRaises(ValueError):
            self.config_manager.set_polling_interval_minutes(1.5)

        with self.assertRaises(ValueError):
            self.config_manager.set_polling_interval_minutes("1")

        with self.assertRaises(ValueError):
            self.config_manager.set_polling_interval_minutes(None)

    def test_get_all_config(self):
        """Test getting all configuration as dictionary."""
        config_dict = self.config_manager.get_all_config()

        # Check that all expected keys are present
        expected_keys = {"model", "enable_continuous_polling", "polling_interval_minutes"}
        self.assertEqual(set(config_dict.keys()), expected_keys)

        # Check that values match getter methods
        self.assertEqual(config_dict["model"], self.config_manager.get_model())
        self.assertEqual(
            config_dict["enable_continuous_polling"],
            self.config_manager.get_enable_continuous_polling(),
        )
        self.assertEqual(
            config_dict["polling_interval_minutes"],
            self.config_manager.get_polling_interval_minutes(),
        )

        # Ensure it's a copy (modifying shouldn't affect internal config)
        config_dict["model"] = "modified"
        self.assertNotEqual(self.config_manager.get_model(), "modified")

    def test_update_config(self):
        """Test updating configuration with dictionary."""
        update_dict = {
            "model": "updated/model",
            "enable_continuous_polling": True,
            "polling_interval_minutes": 10,
        }

        self.config_manager.update_config(update_dict)

        self.assertEqual(self.config_manager.get_model(), "updated/model")
        self.assertTrue(self.config_manager.get_enable_continuous_polling())
        self.assertEqual(self.config_manager.get_polling_interval_minutes(), 10)

    def test_update_config_validation(self):
        """Test that update_config validates values."""
        # Test invalid model
        with self.assertRaises(ValueError):
            self.config_manager.update_config({"model": ""})

        # Test invalid polling interval
        with self.assertRaises(ValueError):
            self.config_manager.update_config({"polling_interval_minutes": 0})

        # Test unknown key
        with self.assertRaises(ValueError):
            self.config_manager.update_config({"unknown_key": "value"})

    def test_validate_config(self):
        """Test configuration validation method."""
        # Should be valid with defaults
        self.assertTrue(self.config_manager.validate_config())

        # Should be valid with custom valid values
        self.config_manager.set_model("custom/model")
        self.config_manager.set_enable_continuous_polling(True)
        self.config_manager.set_polling_interval_minutes(5)
        self.assertTrue(self.config_manager.validate_config())

    @patch.dict(
        os.environ,
        {
            "AI_MODEL": "env/test-model",
            "ENABLE_CONTINUOUS_POLLING": "true",
            "POLLING_INTERVAL_MINUTES": "5",
        },
    )
    def test_environment_variable_loading(self):
        """Test loading configuration from environment variables."""
        config_manager = ConfigurationManager()

        self.assertEqual(config_manager.get_model(), "env/test-model")
        self.assertTrue(config_manager.get_enable_continuous_polling())
        self.assertEqual(config_manager.get_polling_interval_minutes(), 5)

    @patch.dict(os.environ, {"ENABLE_CONTINUOUS_POLLING": "false"})
    def test_environment_boolean_false_values(self):
        """Test that boolean false values from environment are handled correctly."""
        config_manager = ConfigurationManager()
        self.assertFalse(config_manager.get_enable_continuous_polling())

    @patch.dict(os.environ, {"ENABLE_CONTINUOUS_POLLING": "1"})
    def test_environment_boolean_truthy_values(self):
        """Test various truthy values for boolean environment variables."""
        config_manager = ConfigurationManager()
        self.assertTrue(config_manager.get_enable_continuous_polling())

    @patch.dict(os.environ, {"POLLING_INTERVAL_MINUTES": "invalid"})
    def test_invalid_environment_polling_interval(self):
        """Test that invalid polling interval from environment raises error."""
        with self.assertRaises(ValueError):
            ConfigurationManager()

    @patch.dict(os.environ, {"POLLING_INTERVAL_MINUTES": "0"})
    def test_invalid_environment_polling_interval_zero(self):
        """Test that zero polling interval from environment raises error."""
        with self.assertRaises(ValueError):
            ConfigurationManager()


if __name__ == "__main__":
    # Run the tests
    unittest.main()

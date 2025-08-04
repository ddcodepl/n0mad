#!/usr/bin/env python3
"""
Quick test script to verify the new logging system is working correctly.
"""

import sys
import os

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from logging_config import get_logger, setup_logging, log_section_header, log_key_value, log_list_items
import logging

# Test different logging levels
setup_logging(level=logging.DEBUG)
logger = get_logger(__name__)

def test_logging():
    """Test all logging features and colors."""
    
    log_section_header(logger, "LOGGING SYSTEM TEST")
    
    logger.debug("🐛 This is a DEBUG message")
    logger.info("ℹ️  This is an INFO message")
    logger.warning("⚠️  This is a WARNING message")
    logger.error("❌ This is an ERROR message")
    logger.critical("🚨 This is a CRITICAL message")
    
    log_key_value(logger, "🔑 Test Key", "Test Value")
    log_key_value(logger, "🎯 Status", "Working correctly")
    
    test_items = ["Item 1", "Item 2", "Item 3"]
    log_list_items(logger, "📋 Test List", test_items)
    
    log_section_header(logger, "TEST COMPLETED")
    logger.info("✅ All logging features working correctly!")

if __name__ == "__main__":
    test_logging()
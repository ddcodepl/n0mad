#!/usr/bin/env python3
"""
Debug script to analyze Notion database schema and test status filtering.
Run this to identify the correct property types and filter formats.
"""

import os
import sys
from dotenv import load_dotenv

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from notion_wrapper import NotionClientWrapper
from database_operations import DatabaseOperations
from task_status import TaskStatus
from logging_config import get_logger, setup_logging, log_section_header, log_key_value

# Set up debug-level logging to see all details
setup_logging(level=10)  # DEBUG level
logger = get_logger(__name__)

def main():
    """Main debug function to analyze schema and test filters."""
    
    log_section_header(logger, "NOTION DATABASE SCHEMA ANALYSIS")
    
    try:
        # Load environment variables
        load_dotenv()
        
        # Initialize Notion client
        logger.info("🚀 Step 1: Initializing Notion client...")
        notion_client = NotionClientWrapper()
        
        # Test basic connection
        logger.info("🔗 Step 2: Testing connection...")
        if not notion_client.test_connection():
            logger.error("❌ Connection failed!")
            return
        logger.info("✅ Connection successful!")
        
        # Debug database schema
        logger.info("🔍 Step 3: Analyzing database schema...")
        database_info = notion_client.debug_database_schema()
        
        # Test status property detection
        logger.info("🎯 Step 4: Testing status property detection...")
        try:
            prop_type, prop_config = notion_client.get_status_property_type()
            log_key_value(logger, "✅ Status property detected", f"type={prop_type}")
        except Exception as e:
            logger.error(f"❌ Status property detection failed: {e}")
            return
        
        # Test filter creation for different status values
        logger.info("🛠️  Step 5: Testing filter creation...")
        test_statuses = [
            TaskStatus.TO_REFINE,
            TaskStatus.REFINED,
            TaskStatus.IN_PROGRESS,
            TaskStatus.DONE
        ]
        
        for status in test_statuses:
            try:
                filter_dict = notion_client.create_status_filter(status.value)
                log_key_value(logger, f"✅ Filter for '{status.value}'", str(filter_dict))
            except Exception as e:
                logger.error(f"❌ Filter creation failed for '{status.value}': {e}")
        
        # Test actual database query
        logger.info("🔄 Step 6: Testing database query with new filters...")
        db_ops = DatabaseOperations(notion_client)
        
        try:
            # Try to get tasks with "To Refine" status
            tasks = db_ops.get_tasks_to_refine()
            log_key_value(logger, "✅ Successfully queried 'To Refine' tasks", f"found {len(tasks)} tasks")
            
            # Show first task details if any exist
            if tasks:
                first_task = tasks[0]
                log_key_value(logger, "📄 Sample task", f"'{first_task.get('title', 'Untitled')}'")
                log_key_value(logger, "🆔 Task ID", first_task['id'])
                log_key_value(logger, "🔗 URL", first_task['url'])
        except Exception as e:
            logger.error(f"❌ Database query failed: {e}")
        
        # Test query for all tasks to verify basic functionality
        logger.info("📊 Step 7: Testing query for all tasks...")
        try:
            all_tasks = db_ops.get_all_tasks()
            log_key_value(logger, "✅ Successfully retrieved all tasks", f"found {len(all_tasks)} total tasks")
        except Exception as e:
            logger.error(f"❌ Failed to retrieve all tasks: {e}")
        
        log_section_header(logger, "ANALYSIS COMPLETED")
        logger.info("🎉 Schema analysis completed successfully!")
        logger.info("📋 Check the detailed log output above for property information.")
        
    except Exception as e:
        logger.error(f"❌ Debug script failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
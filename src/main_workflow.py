#!/usr/bin/env python3
"""
Main workflow script for Notion API integration with task-master
This script demonstrates the complete end-to-end process:
1. Query Notion for tickets with 'Prepare Tasks' status
2. Extract ticket IDs from page properties
3. Validate corresponding markdown files exist
4. Update ticket status to 'Preparing Tasks'
5. Execute task-master parse-prd commands
6. Copy generated tasks.json files
7. Upload JSON files to Notion page Tasks property
8. Finalize ticket status to 'Ready to Run'
"""
import sys
import os
from typing import List, Dict, Any

# Add src directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from notion_wrapper import NotionClientWrapper
from file_operations import FileOperations
from command_executor import CommandExecutor
from logging_config import get_logger

logger = get_logger(__name__)


class NotionTaskMasterWorkflow:
    def __init__(self):
        """Initialize the workflow with required components"""
        self.notion = NotionClientWrapper()
        # Task-master needs to run from project root where .taskmaster is located
        self.project_root = os.path.dirname(os.path.dirname(__file__))  # Go up from src to project root
        # Initialize both FileOperations and CommandExecutor with the same project root context
        self.file_ops = FileOperations(base_dir=os.path.join(self.project_root, "src", "tasks"))
        self.cmd_executor = CommandExecutor(base_dir=self.project_root)
        
        logger.info("🚀 NotionTaskMasterWorkflow initialized")
    
    def run_complete_workflow(self) -> Dict[str, Any]:
        """
        Execute the complete workflow from start to finish.
        
        Returns:
            Dictionary with complete workflow results
        """
        workflow_results = {
            "step_results": {},
            "overall_success": False,
            "successful_tickets": [],
            "failed_tickets": [],
            "summary": {}
        }
        
        try:
            logger.info("🎬 Starting complete Notion-TaskMaster workflow...")
            
            # Step 1: Query tickets with 'Prepare Tasks' status
            logger.info("📋 Step 1: Querying tickets with 'Prepare Tasks' status...")
            prepare_tasks_pages = self.notion.query_tickets_by_status("Prepare Tasks")
            workflow_results["step_results"]["query_tickets"] = {
                "pages_found": len(prepare_tasks_pages),
                "pages": prepare_tasks_pages
            }
            
            if not prepare_tasks_pages:
                logger.info("ℹ️  No tickets found with 'Prepare Tasks' status")
                workflow_results["summary"] = {
                    "message": "No tickets to process",
                    "total_tickets": 0,
                    "successful_tickets": 0,
                    "failed_tickets": 0
                }
                return workflow_results
            
            # Step 2: Extract ticket IDs
            logger.info("🔍 Step 2: Extracting ticket IDs from page properties...")
            ticket_ids = self.notion.extract_ticket_ids(prepare_tasks_pages)
            workflow_results["step_results"]["extract_ids"] = {
                "extracted_ids": ticket_ids,
                "count": len(ticket_ids)
            }
            
            # Step 3: Validate files exist
            logger.info("📁 Step 3: Validating corresponding markdown files exist...")
            valid_ticket_ids = self.file_ops.validate_task_files(ticket_ids)
            workflow_results["step_results"]["validate_files"] = {
                "valid_ids": valid_ticket_ids,
                "valid_count": len(valid_ticket_ids),
                "invalid_count": len(ticket_ids) - len(valid_ticket_ids)
            }
            
            if not valid_ticket_ids:
                logger.warning("⚠️ No valid ticket files found")
                workflow_results["summary"] = {
                    "message": "No valid tickets to process",
                    "total_tickets": len(ticket_ids),
                    "successful_tickets": 0,
                    "failed_tickets": len(ticket_ids)
                }
                return workflow_results
            
            # Create mapping of valid tickets to their page data
            valid_page_data = []
            for page in prepare_tasks_pages:
                page_ticket_ids = self.notion.extract_ticket_ids([page])
                if page_ticket_ids and page_ticket_ids[0] in valid_ticket_ids:
                    valid_page_data.append({
                        "page_id": page["id"],
                        "ticket_id": page_ticket_ids[0],
                        "page_data": page
                    })
            
            # Step 4: Update status to 'Preparing Tasks'
            logger.info("🔄 Step 4: Updating ticket status to 'Preparing Tasks'...")
            page_ids = [item["page_id"] for item in valid_page_data]
            status_update_results = self.notion.update_tickets_status_batch(page_ids, "Preparing Tasks")
            workflow_results["step_results"]["update_to_preparing"] = status_update_results
            
            # Step 5: Execute task-master commands
            logger.info("⚡ Step 5: Executing task-master parse-prd commands...")
            command_results = self.cmd_executor.execute_taskmaster_command(valid_ticket_ids)
            workflow_results["step_results"]["execute_commands"] = command_results
            
            # Step 6: Copy tasks.json files
            logger.info("📋 Step 6: Copying generated tasks.json files...")
            successful_ticket_ids = [item["ticket_id"] for item in command_results["successful_executions"]]
            # Construct path to .taskmaster/tasks/tasks.json relative to FileOperations base_dir
            taskmaster_tasks_path = os.path.join(self.project_root, ".taskmaster", "tasks", "tasks.json")
            # Construct absolute path to tasks subdirectory  
            tasks_dest_dir = os.path.join(self.project_root, "src", "tasks", "tasks")
            copy_results = self.file_ops.copy_tasks_file(successful_ticket_ids, source_path=taskmaster_tasks_path, dest_dir=tasks_dest_dir)
            workflow_results["step_results"]["copy_files"] = copy_results
            
            # Step 7: Upload JSON files to Notion pages
            logger.info("📤 Step 7: Uploading JSON files to Notion page Tasks property...")
            # Prepare data for upload
            upload_data = []
            for ticket_data in valid_page_data:
                ticket_id = ticket_data["ticket_id"]
                if ticket_id in successful_ticket_ids:
                    # Get the full ticket ID format for the file path
                    full_ticket_id = self.file_ops._get_full_ticket_id(ticket_id)
                    upload_data.append({
                        "ticket_id": ticket_id,
                        "page_id": ticket_data["page_id"],
                        "tasks_file_path": os.path.join(self.project_root, "src", "tasks", "tasks", f"{full_ticket_id}.json")
                    })
            
            upload_results = self.notion.upload_tasks_files_to_pages(upload_data)
            workflow_results["step_results"]["upload_files"] = upload_results
            
            # Step 8: Finalize status to 'Ready to Run'
            logger.info("🏁 Step 8: Finalizing ticket status to 'Ready to Run'...")
            successful_upload_data = []
            for upload_item in upload_results["successful_uploads"]:
                # Find the corresponding ticket data
                for ticket_data in valid_page_data:
                    if ticket_data["ticket_id"] == upload_item["ticket_id"]:
                        successful_upload_data.append({
                            "ticket_id": upload_item["ticket_id"],
                            "page_id": upload_item["page_id"],
                            "tasks_file_path": upload_item["file_path"]
                        })
                        break
            
            finalize_results = self.notion.finalize_ticket_status(successful_upload_data)
            workflow_results["step_results"]["finalize_status"] = finalize_results
            
            # Compile overall results
            total_tickets = len(prepare_tasks_pages)
            successful_tickets = finalize_results["success_count"]
            failed_tickets = total_tickets - successful_tickets
            
            workflow_results["overall_success"] = successful_tickets > 0
            workflow_results["successful_tickets"] = [item["ticket_id"] for item in finalize_results["finalized_tickets"]]
            workflow_results["failed_tickets"] = [item["ticket_id"] for item in finalize_results["failed_finalizations"]]
            
            workflow_results["summary"] = {
                "message": f"Workflow completed: {successful_tickets} successful, {failed_tickets} failed",
                "total_tickets": total_tickets,
                "successful_tickets": successful_tickets,
                "failed_tickets": failed_tickets,
                "success_rate": (successful_tickets / total_tickets * 100) if total_tickets > 0 else 0
            }
            
            # Final summary logging
            logger.info("🎉 Complete workflow finished!")
            logger.info(f"📊 Final Summary:")
            logger.info(f"   📋 Total tickets processed: {total_tickets}")
            logger.info(f"   ✅ Successful completions: {successful_tickets}")
            logger.info(f"   ❌ Failed completions: {failed_tickets}")
            logger.info(f"   📊 Success rate: {workflow_results['summary']['success_rate']:.1f}%")
            
            if workflow_results["successful_tickets"]:
                logger.info(f"   🎯 Successful ticket IDs: {workflow_results['successful_tickets']}")
            
            if workflow_results["failed_tickets"]:
                logger.warning(f"   ⚠️ Failed ticket IDs: {workflow_results['failed_tickets']}")
            
        except Exception as e:
            logger.error(f"❌ Workflow failed with error: {e}")
            workflow_results["summary"] = {
                "message": f"Workflow failed: {str(e)}",
                "total_tickets": 0,
                "successful_tickets": 0,
                "failed_tickets": 0,
                "error": str(e)
            }
        
        return workflow_results


def main():
    """Main entry point for the workflow"""
    try:
        workflow = NotionTaskMasterWorkflow()
        results = workflow.run_complete_workflow()
        
        # Exit with appropriate code
        if results["overall_success"]:
            logger.info("✅ Workflow completed successfully")
            sys.exit(0)
        else:
            logger.error("❌ Workflow completed with errors")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"❌ Fatal error in workflow: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
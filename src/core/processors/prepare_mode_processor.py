"""
Prepare mode processor - extracted from main.py for better separation of concerns.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ...utils.file_operations import get_tasks_dir
from ...utils.logging_config import get_logger
from ...utils.singleton_config import get_config
from ..exceptions import ProcessingError, ValidationError

logger = get_logger(__name__)


class PrepareTasksProcessor:
    """Handles the prepare tasks workflow with proper separation of concerns."""

    def __init__(self, notion_client, cmd_executor, file_ops, project_root: str):
        """
        Initialize processor with required dependencies.

        Args:
            notion_client: Notion client instance
            cmd_executor: Command executor instance
            file_ops: File operations instance
            project_root: Project root directory
        """
        self.notion_client = notion_client
        self.cmd_executor = cmd_executor
        self.file_ops = file_ops
        self.project_root = project_root
        self.config = get_config()

    def process_prepare_tasks(self) -> Dict[str, Any]:
        """
        Main entry point for prepare tasks processing.

        Returns:
            Dictionary with processing results
        """
        workflow_results = self._initialize_workflow_results()

        try:
            logger.info("🎬 Starting complete Notion-TaskMaster workflow...")

            # Execute workflow steps
            prepare_tasks_pages = self._query_prepare_tasks()
            workflow_results["step_results"]["query_tickets"] = {
                "pages_found": len(prepare_tasks_pages),
                "pages": prepare_tasks_pages,
            }

            if not prepare_tasks_pages:
                return self._handle_no_tasks_found(workflow_results)

            ticket_ids = self._extract_ticket_ids(prepare_tasks_pages, workflow_results)
            valid_ticket_ids, valid_page_data = self._validate_and_filter_tickets(ticket_ids, prepare_tasks_pages, workflow_results)

            if not valid_ticket_ids:
                return self._handle_no_valid_tickets(workflow_results, ticket_ids)

            # Process single ticket to avoid conflicts
            selected_ticket_id, selected_page_data = self._select_single_ticket(valid_ticket_ids, valid_page_data)

            # Execute workflow steps
            self._update_status_to_preparing(selected_page_data, workflow_results)
            self._execute_taskmaster_commands([selected_ticket_id], workflow_results)
            self._handle_command_results(workflow_results, selected_page_data)
            self._upload_task_files(workflow_results, selected_page_data)
            self._finalize_workflow(workflow_results, selected_page_data)

            # Generate final summary
            self._generate_final_summary(workflow_results, len(prepare_tasks_pages))

        except Exception as e:
            logger.error(f"❌ Workflow failed with error: {e}")
            workflow_results["summary"] = self._create_error_summary(str(e))

        return workflow_results

    def _initialize_workflow_results(self) -> Dict[str, Any]:
        """Initialize workflow results structure."""
        return {
            "step_results": {},
            "overall_success": False,
            "successful_tickets": [],
            "failed_tickets": [],
            "summary": {},
        }

    def _query_prepare_tasks(self) -> List[Dict[str, Any]]:
        """Query tickets with 'Prepare Tasks' status."""
        logger.info("📋 Step 1: Querying tickets with 'Prepare Tasks' status...")
        return self.notion_client.query_tickets_by_status("Prepare Tasks")

    def _handle_no_tasks_found(self, workflow_results: Dict[str, Any]) -> Dict[str, Any]:
        """Handle case when no tasks are found."""
        logger.info("ℹ️  No tickets found with 'Prepare Tasks' status")
        workflow_results["summary"] = {
            "message": "No tickets to process",
            "total_tickets": 0,
            "successful_tickets": 0,
            "failed_tickets": 0,
        }
        return workflow_results

    def _extract_ticket_ids(self, prepare_tasks_pages: List[Dict[str, Any]], workflow_results: Dict[str, Any]) -> List[str]:
        """Extract ticket IDs from pages."""
        logger.info("🔍 Step 2: Extracting ticket IDs from page properties...")
        ticket_ids = self.notion_client.extract_ticket_ids(prepare_tasks_pages)
        workflow_results["step_results"]["extract_ids"] = {
            "extracted_ids": ticket_ids,
            "count": len(ticket_ids),
        }
        return ticket_ids

    def _validate_and_filter_tickets(
        self,
        ticket_ids: List[str],
        prepare_tasks_pages: List[Dict[str, Any]],
        workflow_results: Dict[str, Any],
    ) -> Tuple[List[str], List[Dict[str, Any]]]:
        """Validate ticket files and create page data mapping."""
        logger.info("📁 Step 3: Validating corresponding markdown files exist...")

        valid_ticket_ids = self.file_ops.validate_task_files(ticket_ids)
        workflow_results["step_results"]["validate_files"] = {
            "valid_ids": valid_ticket_ids,
            "valid_count": len(valid_ticket_ids),
            "invalid_count": len(ticket_ids) - len(valid_ticket_ids),
        }

        # Create mapping of valid tickets to their page data
        valid_page_data = []
        for page in prepare_tasks_pages:
            page_ticket_ids = self.notion_client.extract_ticket_ids([page])
            if page_ticket_ids and page_ticket_ids[0] in valid_ticket_ids:
                valid_page_data.append({"page_id": page["id"], "ticket_id": page_ticket_ids[0], "page_data": page})

        return valid_ticket_ids, valid_page_data

    def _handle_no_valid_tickets(self, workflow_results: Dict[str, Any], ticket_ids: List[str]) -> Dict[str, Any]:
        """Handle case when no valid tickets are found."""
        logger.warning("⚠️ No valid ticket files found")
        workflow_results["summary"] = {
            "message": "No valid tickets to process",
            "total_tickets": len(ticket_ids),
            "successful_tickets": 0,
            "failed_tickets": len(ticket_ids),
        }
        return workflow_results

    def _select_single_ticket(self, valid_ticket_ids: List[str], valid_page_data: List[Dict[str, Any]]) -> Tuple[str, List[Dict[str, Any]]]:
        """Select single ticket to avoid tasks.json conflicts."""
        if len(valid_ticket_ids) > 1:
            logger.info(f"📝 Found {len(valid_ticket_ids)} valid tickets. Processing only the first one to avoid tasks.json conflicts.")
            logger.info(f"🔄 Remaining tickets will be processed in subsequent runs: {valid_ticket_ids[1:]}")
            selected_ticket_id = valid_ticket_ids[0]
            # Filter page data for selected ticket
            selected_page_data = [item for item in valid_page_data if item["ticket_id"] == selected_ticket_id]
        else:
            selected_ticket_id = valid_ticket_ids[0]
            selected_page_data = valid_page_data

        logger.info(f"🎯 Processing single ticket: {selected_ticket_id}")
        return selected_ticket_id, selected_page_data

    def _update_status_to_preparing(self, page_data: List[Dict[str, Any]], workflow_results: Dict[str, Any]) -> None:
        """Update ticket status to 'Preparing Tasks'."""
        logger.info("🔄 Step 4: Updating ticket status to 'Preparing Tasks'...")
        page_ids = [item["page_id"] for item in page_data]
        status_update_results = self.notion_client.update_tickets_status_batch(page_ids, "Preparing Tasks")
        workflow_results["step_results"]["update_to_preparing"] = status_update_results

    def _execute_taskmaster_commands(self, ticket_ids: List[str], workflow_results: Dict[str, Any]) -> None:
        """Execute task-master parse-prd commands."""
        logger.info("⚡ Step 5: Executing task-master parse-prd commands...")
        command_results = self.cmd_executor.execute_taskmaster_command(ticket_ids)
        workflow_results["step_results"]["execute_commands"] = command_results

    def _handle_command_results(self, workflow_results: Dict[str, Any], page_data: List[Dict[str, Any]]) -> None:
        """Handle task-master command execution results."""
        command_results = workflow_results["step_results"]["execute_commands"]
        successful_ticket_ids = [item["ticket_id"] for item in command_results["successful_executions"]]

        if not successful_ticket_ids:
            self._handle_parsing_failure(workflow_results, command_results, page_data)
            return

        # Copy tasks.json files for successful tickets
        self._copy_tasks_files(successful_ticket_ids, workflow_results)

        # Handle failed tickets
        self._handle_failed_tickets(command_results, page_data, workflow_results)

    def _handle_parsing_failure(
        self,
        workflow_results: Dict[str, Any],
        command_results: Dict[str, Any],
        page_data: List[Dict[str, Any]],
    ) -> None:
        """Handle case when no tickets were successfully parsed."""
        logger.warning("⚠️ No tickets were successfully parsed - cannot proceed with copying files")

        failed_ticket_ids = [item["ticket_id"] for item in command_results["failed_executions"]]
        if failed_ticket_ids:
            self._mark_tickets_as_failed(failed_ticket_ids, page_data)

        workflow_results["summary"] = {
            "message": "Task parsing failed - no valid tasks generated",
            "total_tickets": len(page_data),
            "successful_tickets": 0,
            "failed_tickets": len(page_data),
            "error": "Task parsing validation failed",
        }

    def _copy_tasks_files(self, successful_ticket_ids: List[str], workflow_results: Dict[str, Any]) -> None:
        """Copy generated tasks.json files."""
        logger.info("📋 Step 6: Copying generated tasks.json files...")

        taskmaster_tasks_path = os.path.join(self.project_root, ".taskmaster", "tasks", "tasks.json")
        tasks_dest_dir = os.path.join(get_tasks_dir(), "tasks")

        copy_results = self.file_ops.copy_tasks_file(successful_ticket_ids, source_path=taskmaster_tasks_path, dest_dir=tasks_dest_dir)
        workflow_results["step_results"]["copy_files"] = copy_results

    def _handle_failed_tickets(
        self,
        command_results: Dict[str, Any],
        page_data: List[Dict[str, Any]],
        workflow_results: Dict[str, Any],
    ) -> None:
        """Mark failed tickets with appropriate status."""
        failed_ticket_ids = [item["ticket_id"] for item in command_results["failed_executions"]]
        if failed_ticket_ids:
            logger.warning(f"⚠️ {len(failed_ticket_ids)} tickets failed parsing - marking as 'Failed'...")
            self._mark_tickets_as_failed(failed_ticket_ids, page_data)
            workflow_results["step_results"]["mark_failed"] = {"processed": len(failed_ticket_ids)}

    def _mark_tickets_as_failed(self, failed_ticket_ids: List[str], page_data: List[Dict[str, Any]]) -> None:
        """Mark specified tickets as failed."""
        failed_page_ids = []
        for ticket_data in page_data:
            if ticket_data["ticket_id"] in failed_ticket_ids:
                failed_page_ids.append(ticket_data["page_id"])

        if failed_page_ids:
            revert_results = self.notion_client.update_tickets_status_batch(failed_page_ids, "Failed")
            logger.info(f"❌ Marked {revert_results.get('success_count', 0)} tickets as 'Failed'")

    def _upload_task_files(self, workflow_results: Dict[str, Any], page_data: List[Dict[str, Any]]) -> None:
        """Upload JSON files to Notion pages."""
        logger.info("📤 Step 7: Uploading JSON files to Notion page Tasks property...")

        command_results = workflow_results["step_results"]["execute_commands"]
        successful_ticket_ids = [item["ticket_id"] for item in command_results["successful_executions"]]

        upload_data = self._prepare_upload_data(successful_ticket_ids, page_data)
        upload_results = self.notion_client.upload_tasks_files_to_pages(upload_data)
        workflow_results["step_results"]["upload_files"] = upload_results

    def _prepare_upload_data(self, successful_ticket_ids: List[str], page_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepare data for file upload."""
        upload_data = []
        for ticket_data in page_data:
            ticket_id = ticket_data["ticket_id"]
            if ticket_id in successful_ticket_ids:
                full_ticket_id = self.file_ops._get_full_ticket_id(ticket_id)
                upload_data.append(
                    {
                        "ticket_id": ticket_id,
                        "page_id": ticket_data["page_id"],
                        "tasks_file_path": os.path.join(get_tasks_dir(), "tasks", f"{full_ticket_id}.json"),
                    }
                )
        return upload_data

    def _finalize_workflow(self, workflow_results: Dict[str, Any], page_data: List[Dict[str, Any]]) -> None:
        """Finalize ticket status to 'Ready to Run'."""
        logger.info("🏁 Step 8: Finalizing ticket status to 'Ready to Run'...")

        upload_results = workflow_results["step_results"]["upload_files"]
        successful_upload_data = self._prepare_finalization_data(upload_results, page_data)

        finalize_results = self.notion_client.finalize_ticket_status(successful_upload_data)
        workflow_results["step_results"]["finalize_status"] = finalize_results

        # Update workflow results
        self._update_workflow_results(workflow_results, finalize_results)

    def _prepare_finalization_data(self, upload_results: Dict[str, Any], page_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Prepare data for finalization."""
        successful_upload_data = []
        for upload_item in upload_results["successful_uploads"]:
            for ticket_data in page_data:
                if ticket_data["ticket_id"] == upload_item["ticket_id"]:
                    successful_upload_data.append(
                        {
                            "ticket_id": upload_item["ticket_id"],
                            "page_id": upload_item["page_id"],
                            "tasks_file_path": upload_item["file_path"],
                        }
                    )
                    break
        return successful_upload_data

    def _update_workflow_results(self, workflow_results: Dict[str, Any], finalize_results: Dict[str, Any]) -> None:
        """Update workflow results with finalization data."""
        workflow_results["overall_success"] = finalize_results["success_count"] > 0
        workflow_results["successful_tickets"] = [item["ticket_id"] for item in finalize_results["finalized_tickets"]]
        workflow_results["failed_tickets"] = [item["ticket_id"] for item in finalize_results["failed_finalizations"]]

    def _generate_final_summary(self, workflow_results: Dict[str, Any], total_tickets: int) -> None:
        """Generate final workflow summary."""
        successful_tickets = len(workflow_results["successful_tickets"])
        failed_tickets = total_tickets - successful_tickets

        workflow_results["summary"] = {
            "message": f"Workflow completed: {successful_tickets} successful, {failed_tickets} failed",
            "total_tickets": total_tickets,
            "successful_tickets": successful_tickets,
            "failed_tickets": failed_tickets,
            "success_rate": (successful_tickets / total_tickets * 100) if total_tickets > 0 else 0,
        }

        self._log_final_summary(workflow_results, successful_tickets, failed_tickets, total_tickets)

    def _log_final_summary(
        self,
        workflow_results: Dict[str, Any],
        successful_tickets: int,
        failed_tickets: int,
        total_tickets: int,
    ) -> None:
        """Log final summary."""
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

    def _create_error_summary(self, error_message: str) -> Dict[str, Any]:
        """Create error summary."""
        return {
            "message": f"Workflow failed: {error_message}",
            "total_tickets": 0,
            "successful_tickets": 0,
            "failed_tickets": 0,
            "error": error_message,
        }

#!/usr/bin/env python3
"""
Integration tests for branch creation functionality within task processing pipeline.

Tests the complete integration between branch creation and task processing.
"""
import unittest
import tempfile
import shutil
from unittest.mock import patch, MagicMock, call
from datetime import datetime

from core.processors.branch_integrated_processor import (
    BranchIntegratedProcessor,
    BranchIntegratedTaskItem,
    BranchProcessingResult
)
from core.processors.multi_queue_processor import TaskPriority
from core.managers.branch_integration_manager import IntegrationResult
from core.services.branch_service import BranchCreationResult


class TestBranchIntegration(unittest.TestCase):
    """Integration tests for branch creation with task processing."""
    
    def setUp(self):
        """Set up integration test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock dependencies
        self.mock_database_ops = MagicMock()
        self.mock_status_manager = MagicMock()
        self.mock_feedback_manager = MagicMock()
        self.mock_claude_invoker = MagicMock()
        self.mock_task_file_manager = MagicMock()
        
        # Create processor with branch integration enabled
        self.processor = BranchIntegratedProcessor(
            database_ops=self.mock_database_ops,
            status_manager=self.mock_status_manager,
            feedback_manager=self.mock_feedback_manager,
            claude_invoker=self.mock_claude_invoker,
            task_file_manager=self.mock_task_file_manager,
            project_root=self.temp_dir,
            enable_branch_integration=True
        )
    
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_processor_initialization_with_branch_integration(self):
        """Test processor initialization with branch integration enabled."""
        self.assertTrue(self.processor.enable_branch_integration)
        self.assertIsNotNone(self.processor.branch_integration_manager)
        self.assertIsNotNone(self.processor.branch_feedback_manager)
        self.assertIsNotNone(self.processor.branch_config)
    
    def test_processor_initialization_without_branch_integration(self):
        """Test processor initialization with branch integration disabled."""
        processor = BranchIntegratedProcessor(
            database_ops=self.mock_database_ops,
            status_manager=self.mock_status_manager,
            feedback_manager=self.mock_feedback_manager,
            claude_invoker=self.mock_claude_invoker,
            task_file_manager=self.mock_task_file_manager,
            project_root=self.temp_dir,
            enable_branch_integration=False
        )
        
        self.assertFalse(processor.enable_branch_integration)
    
    def create_test_task_item(self, 
                              task_id: str = "TEST-001",
                              title: str = "Test Task",
                              branch_requested: bool = False) -> BranchIntegratedTaskItem:
        """Create a test task item."""
        return BranchIntegratedTaskItem(
            task_id=task_id,
            page_id=f"page_{task_id}",
            title=title,
            priority=TaskPriority.MEDIUM,
            queued_time=datetime.now(),
            branch_requested=branch_requested,
            metadata={
                "taskmaster_task": {
                    "properties": {
                        "New Branch": {
                            "type": "checkbox",
                            "checkbox": branch_requested
                        }
                    }
                }
            }
        )
    
    @patch('core.processors.branch_integrated_processor.get_branch_config')
    def test_analyze_task_branch_requirements_with_checkbox(self, mock_get_config):
        """Test branch requirement analysis when checkbox is checked."""
        # Mock configuration
        mock_config = MagicMock()
        mock_config.enabled = True
        mock_get_config.return_value = mock_config
        
        # Create task with branch request checkbox
        task_item = self.create_test_task_item(branch_requested=True)
        
        # Convert to standard task item for analysis
        from core.processors.multi_queue_processor import QueuedTaskItem
        standard_task = QueuedTaskItem(
            task_id=task_item.task_id,
            page_id=task_item.page_id,
            title=task_item.title,
            priority=task_item.priority,
            queued_time=task_item.queued_time,
            metadata=task_item.metadata
        )
        
        analysis = self.processor._analyze_task_branch_requirements(standard_task)
        
        self.assertTrue(analysis.get("branch_requested", False))
        self.assertIn("preferences", analysis)
    
    @patch('core.processors.branch_integrated_processor.get_branch_config')
    def test_analyze_task_branch_requirements_without_checkbox(self, mock_get_config):
        """Test branch requirement analysis when checkbox is not checked."""
        # Mock configuration
        mock_config = MagicMock()
        mock_config.enabled = True
        mock_get_config.return_value = mock_config
        
        # Create task without branch request
        task_item = self.create_test_task_item(branch_requested=False)
        
        from core.processors.multi_queue_processor import QueuedTaskItem
        standard_task = QueuedTaskItem(
            task_id=task_item.task_id,
            page_id=task_item.page_id,
            title=task_item.title,
            priority=task_item.priority,
            queued_time=task_item.queued_time,
            metadata=task_item.metadata
        )
        
        analysis = self.processor._analyze_task_branch_requirements(standard_task)
        
        self.assertFalse(analysis.get("branch_requested", True))
    
    def test_enhance_tasks_with_branch_metadata(self):
        """Test enhancement of tasks with branch metadata."""
        from core.processors.multi_queue_processor import QueuedTaskItem
        
        # Create standard task items
        standard_tasks = [
            QueuedTaskItem(
                task_id="TEST-001",
                page_id="page_001",
                title="Task with branch",
                priority=TaskPriority.HIGH,
                queued_time=datetime.now(),
                metadata={
                    "taskmaster_task": {
                        "properties": {
                            "New Branch": {"type": "checkbox", "checkbox": True}
                        }
                    }
                }
            ),
            QueuedTaskItem(
                task_id="TEST-002",
                page_id="page_002",
                title="Task without branch",
                priority=TaskPriority.MEDIUM,
                queued_time=datetime.now(),
                metadata={}
            )
        ]
        
        enhanced_tasks = self.processor._enhance_tasks_with_branch_metadata(standard_tasks)
        
        self.assertEqual(len(enhanced_tasks), 2)
        
        # First task should request branch
        self.assertIsInstance(enhanced_tasks[0], BranchIntegratedTaskItem)
        self.assertTrue(enhanced_tasks[0].branch_requested)
        
        # Second task should not request branch
        self.assertIsInstance(enhanced_tasks[1], BranchIntegratedTaskItem)
        self.assertFalse(enhanced_tasks[1].branch_requested)
    
    @patch.object(BranchIntegratedProcessor, '_execute_single_task')
    def test_process_single_task_with_branch_success(self, mock_execute):
        """Test processing a single task with successful branch creation."""
        # Mock successful task execution
        mock_execute.return_value = {
            "status": "success",
            "task_processing_completed": True
        }
        
        # Mock successful branch integration
        with patch.object(self.processor.branch_integration_manager, 'integrate_with_multi_queue_processor') as mock_integrate:
            mock_integrate.return_value = {
                "integration_operation": MagicMock(operation_id="op_123"),
                "branch_created": True,
                "branch_name": "TEST-001-test-task",
                "integration_success": True
            }
            
            task_item = self.create_test_task_item(branch_requested=True)
            result = self.processor._process_single_task_with_branch_integration(task_item)
            
            self.assertEqual(result["status"], BranchProcessingResult.SUCCESS_WITH_BRANCH)
            self.assertTrue(result["branch_integration"]["created"])
            self.assertEqual(result["branch_integration"]["branch_name"], "TEST-001-test-task")
            self.assertIsNotNone(result["branch_integration"]["operation_id"])
    
    @patch.object(BranchIntegratedProcessor, '_execute_single_task')
    def test_process_single_task_with_branch_failure(self, mock_execute):
        """Test processing a single task with failed branch creation."""
        # Mock successful task execution
        mock_execute.return_value = {
            "status": "success",
            "task_processing_completed": True
        }
        
        # Mock failed branch integration
        with patch.object(self.processor.branch_integration_manager, 'integrate_with_multi_queue_processor') as mock_integrate:
            mock_integrate.return_value = {
                "integration_operation": MagicMock(operation_id="op_123", error="Git repo not found"),
                "branch_created": False,
                "branch_name": None,
                "integration_success": False
            }
            
            task_item = self.create_test_task_item(branch_requested=True)
            result = self.processor._process_single_task_with_branch_integration(task_item)
            
            # Should still process task successfully if branch creation fails (depending on config)
            self.assertEqual(result["status"], BranchProcessingResult.SUCCESS)
            self.assertFalse(result["branch_integration"]["created"])
            self.assertEqual(result["branch_integration"]["error"], "Git repo not found")
    
    @patch.object(BranchIntegratedProcessor, '_execute_single_task')
    def test_process_single_task_without_branch_request(self, mock_execute):
        """Test processing a single task without branch request."""
        # Mock successful task execution
        mock_execute.return_value = {
            "status": "success",
            "task_processing_completed": True
        }
        
        task_item = self.create_test_task_item(branch_requested=False)
        result = self.processor._process_single_task_with_branch_integration(task_item)
        
        self.assertEqual(result["status"], BranchProcessingResult.SUCCESS)
        self.assertFalse(result["branch_integration"]["requested"])
        self.assertFalse(result["branch_integration"]["created"])
    
    @patch.object(BranchIntegratedProcessor, '_execute_single_task')
    def test_process_single_task_execution_failure(self, mock_execute):
        """Test processing when task execution fails."""
        # Mock failed task execution
        mock_execute.return_value = {
            "status": "failed",
            "error": "Task processing error"
        }
        
        # Mock successful branch creation
        with patch.object(self.processor.branch_integration_manager, 'integrate_with_multi_queue_processor') as mock_integrate:
            mock_integrate.return_value = {
                "integration_operation": MagicMock(operation_id="op_123"),
                "branch_created": True,
                "branch_name": "TEST-001-test-task",
                "integration_success": True
            }
            
            task_item = self.create_test_task_item(branch_requested=True)
            result = self.processor._process_single_task_with_branch_integration(task_item)
            
            # Should indicate task failed but branch was created
            self.assertEqual(result["status"], BranchProcessingResult.FAILED_TASK_ONLY)
            self.assertTrue(result["branch_integration"]["created"])
            self.assertEqual(result["error"], "Task processing error")
    
    def test_record_processing_result_success_with_branch(self):
        """Test recording processing results with branch operations."""
        result = {
            "task_id": "TEST-001",
            "status": BranchProcessingResult.SUCCESS_WITH_BRANCH,
            "branch_integration": {"created": True}
        }
        
        initial_successful = self.processor._current_session.successful_tasks if self.processor._current_session else 0
        
        # Initialize session for testing
        from core.processors.branch_integrated_processor import BranchIntegratedSession
        self.processor._current_session = BranchIntegratedSession(
            session_id="test_session",
            start_time=datetime.now(),
            processing_results=[],
            error_summary=[],
            branch_integration_stats={}
        )
        
        self.processor._record_processing_result(result)
        
        self.assertEqual(len(self.processor._current_session.processing_results), 1)
        self.assertEqual(self.processor._current_session.successful_tasks, 1)
        self.assertEqual(self.processor._current_session.processed_tasks, 1)
    
    def test_record_processing_result_branch_failure(self):
        """Test recording processing results with branch failures."""
        result = {
            "task_id": "TEST-001",
            "status": BranchProcessingResult.FAILED_BRANCH_ONLY,
            "error": "Branch creation failed"
        }
        
        # Initialize session for testing
        from core.processors.branch_integrated_processor import BranchIntegratedSession
        self.processor._current_session = BranchIntegratedSession(
            session_id="test_session",
            start_time=datetime.now(),
            processing_results=[],
            error_summary=[],
            branch_integration_stats={}
        )
        
        self.processor._record_processing_result(result)
        
        self.assertEqual(len(self.processor._current_session.processing_results), 1)
        self.assertEqual(self.processor._current_session.failed_tasks, 1)
        self.assertEqual(self.processor._current_session.processed_tasks, 1)
    
    def test_create_error_result(self):
        """Test creation of error results."""
        task_item = self.create_test_task_item(
            task_id="TEST-ERROR",
            title="Error task",
            branch_requested=True
        )
        task_item.branch_created = True
        task_item.branch_name = "error-branch"
        task_item.branch_operation_id = "op_error"
        
        error_result = self.processor._create_error_result(task_item, "Test error")
        
        self.assertEqual(error_result["task_id"], "TEST-ERROR")
        self.assertEqual(error_result["status"], BranchProcessingResult.FAILED)
        self.assertEqual(error_result["error"], "Test error")
        self.assertTrue(error_result["branch_integration"]["requested"])
        self.assertTrue(error_result["branch_integration"]["created"])
        self.assertEqual(error_result["branch_integration"]["branch_name"], "error-branch")
    
    def test_get_branch_integration_statistics(self):
        """Test getting comprehensive statistics including branch integration."""
        # Mock branch integration components
        with patch.object(self.processor.branch_integration_manager, 'get_integration_statistics') as mock_int_stats, \
             patch.object(self.processor.branch_feedback_manager, 'get_feedback_statistics') as mock_feed_stats:
            
            mock_int_stats.return_value = {
                "total_integrations": 5,
                "successful_integrations": 4,
                "failed_integrations": 1
            }
            
            mock_feed_stats.return_value = {
                "total_feedback": 10,
                "branches_created": 4
            }
            
            stats = self.processor.get_branch_integration_statistics()
            
            self.assertTrue(stats["branch_integration_enabled"])
            self.assertIn("integration_statistics", stats)
            self.assertIn("feedback_statistics", stats)
            self.assertIn("branch_config", stats)
    
    @patch('core.processors.branch_integrated_processor.get_branch_config')
    def test_full_integration_workflow(self, mock_get_config):
        """Test complete integration workflow from task discovery to completion."""
        # Mock configuration
        mock_config = MagicMock()
        mock_config.enabled = True
        mock_config.fail_task_on_branch_error = False
        mock_get_config.return_value = mock_config
        
        # Mock task discovery
        with patch.object(self.processor, '_discover_and_prioritize_tasks') as mock_discover:
            from core.processors.multi_queue_processor import QueuedTaskItem
            
            mock_tasks = [
                QueuedTaskItem(
                    task_id="WORKFLOW-001",
                    page_id="page_001",
                    title="Integration test task",
                    priority=TaskPriority.HIGH,
                    queued_time=datetime.now(),
                    metadata={
                        "taskmaster_task": {
                            "properties": {
                                "New Branch": {"type": "checkbox", "checkbox": True}
                            }
                        }
                    }
                )
            ]
            mock_discover.return_value = mock_tasks
            
            # Mock task execution
            with patch.object(self.processor, '_execute_single_task') as mock_execute, \
                 patch.object(self.processor.branch_integration_manager, 'integrate_with_multi_queue_processor') as mock_integrate:
                
                mock_execute.return_value = {
                    "status": "success",
                    "completed_successfully": True
                }
                
                mock_integrate.return_value = {
                    "integration_operation": MagicMock(operation_id="workflow_op"),
                    "branch_created": True,
                    "branch_name": "WORKFLOW-001-integration-test-task",
                    "integration_success": True
                }
                
                # Run full workflow
                session = self.processor.process_queued_tasks()
                
                # Verify results
                self.assertEqual(session.total_tasks, 1)
                self.assertEqual(session.processed_tasks, 1)
                self.assertEqual(session.successful_tasks, 1)
                self.assertEqual(len(session.processing_results), 1)
                
                # Verify branch integration occurred
                result = session.processing_results[0]
                self.assertTrue(result["branch_integration"]["created"])
                self.assertEqual(result["branch_integration"]["branch_name"], "WORKFLOW-001-integration-test-task")


class TestBranchIntegrationEdgeCases(unittest.TestCase):
    """Test edge cases and error scenarios for branch integration."""
    
    def setUp(self):
        """Set up edge case test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Mock dependencies
        self.mock_database_ops = MagicMock()
        self.mock_status_manager = MagicMock()
        self.mock_feedback_manager = MagicMock()
        self.mock_claude_invoker = MagicMock()
        self.mock_task_file_manager = MagicMock()
    
    def tearDown(self):
        """Clean up edge case test environment."""
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_branch_integration_initialization_failure(self):
        """Test processor behavior when branch integration fails to initialize."""
        # Create processor with invalid project root
        with patch('core.processors.branch_integrated_processor.get_branch_config', side_effect=Exception("Config error")):
            processor = BranchIntegratedProcessor(
                database_ops=self.mock_database_ops,
                status_manager=self.mock_status_manager,
                feedback_manager=self.mock_feedback_manager,
                claude_invoker=self.mock_claude_invoker,  
                task_file_manager=self.mock_task_file_manager,
                project_root="/invalid/path",
                enable_branch_integration=True
            )
            
            # Should fall back to disabled branch integration
            self.assertFalse(processor.enable_branch_integration)
    
    def test_branch_analysis_exception_handling(self):
        """Test exception handling during branch requirement analysis."""
        processor = BranchIntegratedProcessor(
            database_ops=self.mock_database_ops,
            status_manager=self.mock_status_manager,
            feedback_manager=self.mock_feedback_manager,
            claude_invoker=self.mock_claude_invoker,
            task_file_manager=self.mock_task_file_manager,
            project_root=self.temp_dir,
            enable_branch_integration=False  # Disable to avoid initialization issues
        )
        
        # Mock branch integration manager to raise exception
        processor.enable_branch_integration = True
        processor.branch_integration_manager = MagicMock()
        processor.branch_integration_manager.checkbox_detector.extract_branch_preferences.side_effect = Exception("Analysis error")
        
        from core.processors.multi_queue_processor import QueuedTaskItem
        task_item = QueuedTaskItem(
            task_id="ERROR-001",
            page_id="page_error",
            title="Error task",
            priority=TaskPriority.MEDIUM,
            queued_time=datetime.now()
        )
        
        analysis = processor._analyze_task_branch_requirements(task_item)
        
        self.assertFalse(analysis["branch_requested"])
        self.assertIn("error", analysis)
    
    def test_processing_with_branch_integration_disabled(self):
        """Test that processing works normally when branch integration is disabled."""
        processor = BranchIntegratedProcessor(
            database_ops=self.mock_database_ops,
            status_manager=self.mock_status_manager,
            feedback_manager=self.mock_feedback_manager,
            claude_invoker=self.mock_claude_invoker,
            task_file_manager=self.mock_task_file_manager,
            project_root=self.temp_dir,
            enable_branch_integration=False
        )
        
        task_item = BranchIntegratedTaskItem(
            task_id="NO-BRANCH-001",
            page_id="page_no_branch",
            title="Task without branch integration",
            priority=TaskPriority.MEDIUM,
            queued_time=datetime.now(),
            branch_requested=True  # Even if requested, should be ignored
        )
        
        with patch.object(processor, '_execute_single_task') as mock_execute:
            mock_execute.return_value = {
                "status": "success",
                "completed": True
            }
            
            result = processor._process_single_task_with_branch_integration(task_item)
            
            # Should process normally without branch operations
            self.assertEqual(result["status"], BranchProcessingResult.SUCCESS)
            self.assertFalse(result["branch_integration"]["created"])


if __name__ == '__main__':
    unittest.main()
import os
import sys
import time
import signal
import logging
import asyncio
import concurrent.futures
from datetime import datetime
from dotenv import load_dotenv

from notion_wrapper import NotionClientWrapper
from openai_client import OpenAIClient
from database_operations import DatabaseOperations
from content_processor import ContentProcessor
from file_operations import FileOperations


load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('nomad.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


class NotionDeveloper:
    def __init__(self):
        self.running = True
        self.max_concurrent_tasks = int(os.getenv("MAX_CONCURRENT_TASKS", "3"))  # Configurable via environment
        self.stats = {
            "tasks_processed": 0,
            "tasks_failed": 0,
            "start_time": datetime.now(),
            "last_poll": None
        }
        
        try:
            logger.info("Initializing Notion Developer application...")
            
            self.notion_client = NotionClientWrapper()
            self.openai_client = OpenAIClient()
            self.file_ops = FileOperations()
            self.db_ops = DatabaseOperations(self.notion_client)
            self.processor = ContentProcessor(self.notion_client, self.openai_client, self.file_ops)
            
            if not self.notion_client.test_connection():
                raise Exception("Failed to connect to Notion database")
            
            logger.info("Application initialized successfully")
            logger.info(f"Configured for {self.max_concurrent_tasks} concurrent task processing")
            
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            sys.exit(1)
    
    def signal_handler(self, signum, frame):
        logger.info("Received shutdown signal. Gracefully stopping...")
        self.running = False
    
    def process_task_wrapper(self, task):
        """Wrapper function for concurrent task processing"""
        try:
            # Guard against None tasks
            if task is None:
                logger.error("Received None task in process_task_wrapper")
                return {
                    "page_id": "unknown",
                    "status": "failed",
                    "error": "Task is None"
                }
            
            result = self.processor.process_task(task, lambda: not self.running)
            return result
        except Exception as e:
            logger.error(f"Exception in concurrent task processing: {e}")
            return {
                "page_id": task.get("id", "unknown") if task is not None else "unknown",
                "status": "failed",
                "error": str(e)
            }
    
    def run(self):
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info("Starting main application loop (polling every 60 seconds)...")
        
        while self.running:
            try:
                self.stats["last_poll"] = datetime.now()
                logger.info("="*50)
                logger.info(f"Polling for tasks with 'To Refine' status...")
                
                tasks = self.db_ops.get_tasks_to_refine()
                
                # Filter out None tasks to prevent processing errors
                if tasks:
                    original_count = len(tasks)
                    tasks = [task for task in tasks if task is not None]
                    none_count = original_count - len(tasks)
                    if none_count > 0:
                        logger.warning(f"Filtered out {none_count} None tasks from {original_count} total")
                    
                
                if tasks:
                    logger.info(f"Found {len(tasks)} valid tasks to process concurrently")
                    processing_start_time = datetime.now()
                    
                    # Process tasks concurrently using ThreadPoolExecutor
                    max_concurrent_tasks = min(len(tasks), self.max_concurrent_tasks)
                    logger.info(f"Processing {len(tasks)} tasks with {max_concurrent_tasks} concurrent workers (max configured: {self.max_concurrent_tasks})")
                    
                    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent_tasks) as executor:
                        # Submit all tasks for concurrent processing
                        future_to_task = {
                            executor.submit(self.process_task_wrapper, task): task 
                            for task in tasks
                        }
                        
                        # Process completed tasks as they finish with responsive shutdown checking
                        completed_tasks = 0
                        while completed_tasks < len(tasks) and self.running:
                            try:
                                # Use timeout to check for shutdown periodically
                                done_futures = []
                                for future in concurrent.futures.as_completed(future_to_task, timeout=1.0):
                                    done_futures.append(future)
                                    completed_tasks += 1
                                    break  # Process one task at a time to check shutdown frequently
                                
                                if not done_futures:
                                    continue  # Timeout occurred, check shutdown and continue
                                
                                future = done_futures[0]
                                task = future_to_task[future]
                                
                                try:
                                    result = future.result()
                                    
                                    if result["status"] == "completed":
                                        self.stats["tasks_processed"] += 1
                                        task_display_id = result.get('task_id', result.get('page_id', 'unknown'))
                                        logger.info(f"✅ Task {task_display_id} processed successfully")
                                    elif result["status"] == "failed":
                                        self.stats["tasks_failed"] += 1
                                        task_display_id = result.get('task_id', result.get('page_id', 'unknown'))
                                        logger.error(f"❌ Task {task_display_id} failed: {result.get('error', 'Unknown error')}")
                                    elif result["status"] == "aborted":
                                        task_display_id = result.get('task_id', result.get('page_id', 'unknown'))
                                        logger.info(f"⏹️  Task {task_display_id} aborted due to shutdown")
                                    elif result["status"] == "skipped":
                                        task_display_id = result.get('task_id', result.get('page_id', 'unknown'))
                                        logger.info(f"⏭️  Task {task_display_id} skipped: {result.get('message', 'No reason provided')}")
                                        
                                except concurrent.futures.CancelledError:
                                    logger.info(f"⏹️  Task {task.get('id', 'unknown')} was cancelled due to shutdown")
                                except Exception as e:
                                    self.stats["tasks_failed"] += 1
                                    logger.error(f"❌ Unexpected error processing task {task.get('id', 'unknown')}: {e}")
                                    
                            except concurrent.futures.TimeoutError:
                                # Timeout is expected - allows us to check shutdown flag
                                continue
                        
                        # Cancel any remaining tasks if shutdown was requested
                        if not self.running:
                            logger.info("Shutdown requested, cancelling remaining tasks...")
                            for remaining_future in future_to_task:
                                if not remaining_future.done():
                                    remaining_future.cancel()
                    
                    processing_duration = datetime.now() - processing_start_time
                    logger.info(f"🏁 Completed concurrent processing of {len(tasks)} tasks in {processing_duration}")
                    
                    # Log performance summary
                    if len(tasks) > 1:
                        avg_time_per_task = processing_duration.total_seconds() / len(tasks)
                        logger.info(f"📊 Average processing time per task: {avg_time_per_task:.2f} seconds")
                        logger.info(f"🚀 Concurrent processing efficiency: {max_concurrent_tasks}x parallelization")
                else:
                    logger.info("No tasks found with 'To Refine' status")
                
                self.log_statistics()
                
                if self.running:
                    logger.info("Sleeping for 60 seconds...")
                    for i in range(60):
                        if not self.running:
                            logger.info(f"Shutdown requested, stopping sleep cycle (slept {i} seconds)")
                            break
                        time.sleep(1)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                if self.running:
                    logger.info("Retrying in 60 seconds...")
                    for i in range(60):
                        if not self.running:
                            logger.info(f"Shutdown requested during error recovery (waited {i} seconds)")
                            break
                        time.sleep(1)
        
        logger.info("Application stopped")
        self.log_final_statistics()
    
    def log_statistics(self):
        runtime = datetime.now() - self.stats["start_time"]
        logger.info(f"Statistics - Processed: {self.stats['tasks_processed']}, Failed: {self.stats['tasks_failed']}, Runtime: {runtime}")
    
    def log_final_statistics(self):
        runtime = datetime.now() - self.stats["start_time"]
        logger.info("="*50)
        logger.info("Final Statistics:")
        logger.info(f"  Total runtime: {runtime}")
        logger.info(f"  Tasks processed: {self.stats['tasks_processed']}")
        logger.info(f"  Tasks failed: {self.stats['tasks_failed']}")
        logger.info(f"  Success rate: {self.stats['tasks_processed'] / (self.stats['tasks_processed'] + self.stats['tasks_failed']) * 100 if (self.stats['tasks_processed'] + self.stats['tasks_failed']) > 0 else 0:.2f}%")
        logger.info("="*50)


def main():
    app = NotionDeveloper()
    app.run()


if __name__ == "__main__":
    main()

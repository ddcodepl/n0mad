import logging
import os
import re
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def get_tasks_dir() -> str:
    """
    Get the tasks directory from TASKS_DIR environment variable or default to './tasks'.

    Returns:
        str: Path to the tasks directory
    """
    return os.getenv("TASKS_DIR", "./tasks")


class FileOperations:
    def __init__(self, base_dir: str = None):
        # Load TASKS_DIR from environment variable, with fallback to default
        if base_dir is None:
            base_dir = get_tasks_dir()

        self.base_dir = base_dir
        self.pre_refined_dir = os.path.join(base_dir, "pre-refined")
        self.refined_dir = os.path.join(base_dir, "refined")
        self._ensure_directories_exist()

    def _ensure_directories_exist(self):
        try:
            Path(self.base_dir).mkdir(parents=True, exist_ok=True)
            Path(self.pre_refined_dir).mkdir(parents=True, exist_ok=True)
            Path(self.refined_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"Tasks directory ensured at: {self.base_dir}")
            logger.info(f"Pre-refined directory ensured at: {self.pre_refined_dir}")
            logger.info(f"Refined directory ensured at: {self.refined_dir}")
        except Exception as e:
            logger.error(f"Failed to create tasks directories: {e}")
            raise

    def _sanitize_filename(self, filename: str) -> str:
        sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
        sanitized = sanitized.strip(". ")
        return sanitized[:255]

    def save_to_markdown(self, content: str, page_id: str, title: str = None, property_id: str = None) -> str:
        try:
            # Use property_id if provided, otherwise fall back to page_id
            file_id = property_id if property_id else page_id
            filename = f"{self._sanitize_filename(file_id)}.md"
            filepath = os.path.join(self.base_dir, filename)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            markdown_content = f"---\n"
            markdown_content += f"page_id: {page_id}\n"
            if title:
                markdown_content += f"title: {title}\n"
            markdown_content += f"generated_at: {timestamp}\n"
            markdown_content += f"---\n\n"
            markdown_content += content

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            logger.info(f"Successfully saved content to: {filepath}")
            return filepath

        except IOError as e:
            logger.error(f"Failed to save file {page_id}.md: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error saving file: {e}")
            raise

    def read_markdown(self, page_id: str, property_id: str = None) -> str:
        try:
            # Use property_id if provided, otherwise fall back to page_id
            file_id = property_id if property_id else page_id
            filename = f"{self._sanitize_filename(file_id)}.md"
            filepath = os.path.join(self.base_dir, filename)

            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()

            return content

        except FileNotFoundError:
            logger.warning(f"File not found: {page_id}.md")
            return None
        except Exception as e:
            logger.error(f"Failed to read file {page_id}.md: {e}")
            raise

    def file_exists(self, page_id: str, property_id: str = None) -> bool:
        # Use property_id if provided, otherwise fall back to page_id
        file_id = property_id if property_id else page_id
        filename = f"{self._sanitize_filename(file_id)}.md"
        filepath = os.path.join(self.base_dir, filename)
        return os.path.exists(filepath)

    def save_pre_refined(self, content: str, page_id: str, title: str = None, ticket_id: str = None) -> str:
        """Save original content before refinement"""
        try:
            # Use ticket_id for filename (e.g., NOMAD-14), fallback to page_id
            file_id = ticket_id if ticket_id else page_id
            filename = f"{self._sanitize_filename(file_id)}.md"
            filepath = os.path.join(self.pre_refined_dir, filename)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            markdown_content = f"---\n"
            markdown_content += f"page_id: {page_id}\n"  # Always use the real Notion page ID
            if title:
                markdown_content += f"title: {title}\n"
            if ticket_id:
                markdown_content += f"ticket_id: {ticket_id}\n"  # Use ticket_id instead of property_id
            markdown_content += f"stage: pre-refined\n"
            markdown_content += f"generated_at: {timestamp}\n"
            markdown_content += f"---\n\n"
            markdown_content += content

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            logger.info(f"Successfully saved pre-refined content to: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to save pre-refined file: {e}")
            raise

    def save_refined(self, content: str, page_id: str, title: str = None, ticket_id: str = None) -> str:
        """Save refined content after processing"""
        try:
            # Use ticket_id for filename (e.g., NOMAD-14), fallback to page_id
            file_id = ticket_id if ticket_id else page_id
            filename = f"{self._sanitize_filename(file_id)}.md"
            filepath = os.path.join(self.refined_dir, filename)

            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            markdown_content = f"---\n"
            markdown_content += f"page_id: {page_id}\n"  # Always use the real Notion page ID
            if title:
                markdown_content += f"title: {title}\n"
            if ticket_id:
                markdown_content += f"ticket_id: {ticket_id}\n"  # Use ticket_id instead of property_id
            markdown_content += f"stage: refined\n"
            markdown_content += f"generated_at: {timestamp}\n"
            markdown_content += f"---\n\n"
            markdown_content += content

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            logger.info(f"Successfully saved refined content to: {filepath}")
            return filepath

        except Exception as e:
            logger.error(f"Failed to save refined file: {e}")
            raise

    def validate_task_files(self, ticket_ids: list) -> list:
        """
        Validate that corresponding markdown files exist in tasks/refined/ directory for extracted ticket IDs.

        Args:
            ticket_ids: List of ticket IDs to validate

        Returns:
            List of valid ticket IDs that have corresponding files
        """
        valid_ticket_ids = []
        missing_files = []

        logger.info(f"📁 Validating task files for {len(ticket_ids)} ticket IDs...")

        for ticket_id in ticket_ids:
            try:
                # Check multiple possible filename patterns
                possible_filenames = [
                    f"NOMAD-{ticket_id}.md",  # Pattern: NOMAD-12.md
                    f"{ticket_id}.md",  # Pattern: 12.md
                    f"TICKET-{ticket_id}.md",  # Pattern: TICKET-12.md
                ]

                file_found = False
                found_filepath = None

                for filename in possible_filenames:
                    filepath = os.path.join(self.refined_dir, filename)

                    if os.path.exists(filepath):
                        file_found = True
                        found_filepath = filepath
                        logger.info(f"✅ Found file for ticket {ticket_id}: {filename}")
                        break

                if file_found:
                    valid_ticket_ids.append(ticket_id)
                else:
                    missing_files.append(ticket_id)
                    logger.warning(f"⚠️ No file found for ticket {ticket_id}")
                    logger.debug(f"    Searched for: {', '.join(possible_filenames)}")

            except Exception as e:
                logger.error(f"❌ Error validating ticket {ticket_id}: {e}")
                missing_files.append(ticket_id)

        # Summary logging
        logger.info(f"📊 File validation results:")
        logger.info(f"   ✅ Valid tickets with files: {len(valid_ticket_ids)}")
        logger.info(f"   ❌ Missing files: {len(missing_files)}")

        if valid_ticket_ids:
            logger.info(f"   📋 Valid IDs: {valid_ticket_ids}")

        if missing_files:
            logger.warning(f"   📋 Missing files for IDs: {missing_files}")

            # List existing files for troubleshooting
            try:
                existing_files = [f for f in os.listdir(self.refined_dir) if f.endswith(".md")]
                logger.info(f"   📁 Existing files in {self.refined_dir}: {existing_files}")
            except Exception as e:
                logger.error(f"   ❌ Could not list existing files: {e}")

        return valid_ticket_ids

    def copy_tasks_file(
        self,
        ticket_ids: list,
        source_path: str = ".taskmaster/tasks/tasks.json",
        dest_dir: str = None,
    ) -> dict:
        """
        Copy tasks.json from .taskmaster/tasks/ to tasks/tasks/<id>.json for each processed ticket.

        Args:
            ticket_ids: List of ticket IDs to copy tasks file for
            source_path: Path to source tasks.json file
            dest_dir: Destination directory for copied files (defaults to TASKS_DIR/tasks)

        Returns:
            Dictionary with copy results
        """
        # Use default destination directory if not provided
        if dest_dir is None:
            dest_dir = os.path.join(get_tasks_dir(), "tasks")

        results = {
            "successful_copies": [],
            "failed_copies": [],
            "total_processed": len(ticket_ids),
            "success_count": 0,
            "failure_count": 0,
        }

        logger.info(f"📁 Starting file copying for {len(ticket_ids)} ticket IDs")
        logger.info(f"📄 Source: {source_path}")
        logger.info(f"📁 Destination directory: {dest_dir}")

        # Check if source file exists
        if not os.path.exists(source_path):
            error_msg = f"Source file does not exist: {source_path}"
            logger.error(f"❌ {error_msg}")
            # Mark all as failed
            for ticket_id in ticket_ids:
                results["failed_copies"].append(
                    {
                        "ticket_id": ticket_id,
                        "error": error_msg,
                        "source_path": source_path,
                        "dest_path": "N/A",
                    }
                )
                results["failure_count"] += 1
            return results

        # Ensure destination directory exists
        try:
            Path(dest_dir).mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ Destination directory ensured: {dest_dir}")
        except Exception as e:
            error_msg = f"Failed to create destination directory {dest_dir}: {e}"
            logger.error(f"❌ {error_msg}")
            # Mark all as failed
            for ticket_id in ticket_ids:
                results["failed_copies"].append(
                    {
                        "ticket_id": ticket_id,
                        "error": error_msg,
                        "source_path": source_path,
                        "dest_path": "N/A",
                    }
                )
                results["failure_count"] += 1
            return results

        # Copy file for each ticket ID
        for i, ticket_id in enumerate(ticket_ids):
            try:
                logger.info(f"📄 Copying file for ticket {i+1}/{len(ticket_ids)}: {ticket_id}")

                # Use full ticket ID format (e.g., NOMAD-12 instead of just 12)
                full_ticket_id = self._get_full_ticket_id(ticket_id)
                dest_filename = f"{full_ticket_id}.json"
                dest_path = os.path.join(dest_dir, dest_filename)

                # Perform atomic copy using temporary file
                self._atomic_copy(source_path, dest_path)

                # Verify the copy was successful
                if os.path.exists(dest_path):
                    file_size = os.path.getsize(dest_path)
                    results["successful_copies"].append(
                        {
                            "ticket_id": ticket_id,
                            "source_path": source_path,
                            "dest_path": dest_path,
                            "file_size": file_size,
                        }
                    )
                    results["success_count"] += 1
                    logger.info(f"✅ Successfully copied tasks file for ticket {ticket_id} ({file_size} bytes)")
                else:
                    raise Exception("File copy verification failed - destination file does not exist")

            except Exception as e:
                error_info = {
                    "ticket_id": ticket_id,
                    "error": str(e),
                    "source_path": source_path,
                    "dest_path": dest_path if "dest_path" in locals() else "N/A",
                }
                results["failed_copies"].append(error_info)
                results["failure_count"] += 1

                logger.error(f"❌ Failed to copy tasks file for ticket {ticket_id}: {e}")
                continue

        # Summary logging
        logger.info(f"📊 File copying completed:")
        logger.info(f"   ✅ Successful copies: {results['success_count']}")
        logger.info(f"   ❌ Failed copies: {results['failure_count']}")

        if results["total_processed"] > 0:
            success_rate = results["success_count"] / results["total_processed"] * 100
            logger.info(f"   📊 Success rate: {success_rate:.1f}%")
        else:
            logger.info(f"   📊 Success rate: N/A (no tickets processed)")

        if results["failed_copies"]:
            failed_ids = [f["ticket_id"] for f in results["failed_copies"]]
            logger.warning(f"⚠️ Failed ticket IDs: {failed_ids}")

        return results

    def _atomic_copy(self, source_path: str, dest_path: str):
        """
        Perform atomic file copy using temporary file.

        Args:
            source_path: Source file path
            dest_path: Destination file path
        """
        dest_dir = os.path.dirname(dest_path)
        dest_filename = os.path.basename(dest_path)

        # Create temporary file in the same directory as destination
        # This ensures the move operation is atomic (on same filesystem)
        with tempfile.NamedTemporaryFile(mode="wb", dir=dest_dir, prefix=f".{dest_filename}.tmp", delete=False) as temp_file:
            temp_path = temp_file.name

            try:
                # Copy source to temporary file
                with open(source_path, "rb") as src:
                    shutil.copyfileobj(src, temp_file)

                # Ensure data is written to disk
                temp_file.flush()
                os.fsync(temp_file.fileno())

                # Atomically move temporary file to final destination
                shutil.move(temp_path, dest_path)

                logger.debug(f"🔄 Atomic copy completed: {source_path} -> {dest_path}")

            except Exception as e:
                # Clean up temporary file if something went wrong
                try:
                    os.unlink(temp_path)
                except OSError:
                    pass  # Ignore cleanup errors
                raise e

    def _get_full_ticket_id(self, ticket_id: str) -> str:
        """
        Get the full ticket ID format (e.g., NOMAD-12 instead of just 12).

        Args:
            ticket_id: The ticket ID (could be just numeric or already full format)

        Returns:
            Full ticket ID format
        """
        # If it already contains a hyphen, assume it's already in full format
        if "-" in ticket_id:
            return ticket_id

        # Check if we can find the corresponding file to determine the prefix
        possible_prefixes = ["NOMAD", "TICKET"]

        for prefix in possible_prefixes:
            potential_filename = f"{prefix}-{ticket_id}.md"
            potential_path = os.path.join(self.refined_dir, potential_filename)

            if os.path.exists(potential_path):
                logger.debug(f"📝 Found file pattern for ticket {ticket_id}: {prefix}-{ticket_id}")
                return f"{prefix}-{ticket_id}"

        # Default to NOMAD prefix if no file found
        logger.debug(f"📝 Using default NOMAD prefix for ticket {ticket_id}")
        return f"NOMAD-{ticket_id}"

from enum import Enum


class TaskStatus(str, Enum):
    IDEAS = "Ideas"
    TO_REFINE = "To Refine"
    REFINED = "Refined"
    PREPARE_TASKS = "Prepare Tasks"
    PREPARING_TASKS = "Preparing Tasks"
    QUEUED_TO_RUN = "Queued to run"
    IN_PROGRESS = "In progress"
    FAILED = "Failed"
    DONE = "Done"
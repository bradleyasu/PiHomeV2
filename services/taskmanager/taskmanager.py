import datetime
from threading import Thread
from time import sleep

from util.phlog import PIHOME_LOGGER

is_running = False
class TaskManager():
    def __init__(self):
        self.tasks = []
        if not is_running:
            is_running = True
            Thread(target=self.run_service, daemon=True).start()
            PIHOME_LOGGER.info("Task Manager is has started")
        else:
            PIHOME_LOGGER.warn("Task Manager is already running")

    def add_task(self, task):
        self.tasks.append(task)

    def remove_task(self, task):
        self.tasks.remove(task)

    def get_tasks(self):
        return self.tasks

    def get_task_by_id(self, id):
        for task in self.tasks:
            if task.id == id:
                return task
        return None

    def process_tasks(self):
        for task in self.tasks:
            if task.status == TaskStatus.PENDING:
                if task.start_time <= datetime.now() and task.end_time >= datetime.now():
                    task.status = TaskStatus.IN_PROGRESS
                elif task.end_time < datetime.now():
                    task.status = TaskStatus.COMPLETED
    
    def run_service(self):
        while True:
            self.process_tasks()
            for task in self.tasks:
                if task.status == TaskStatus.IN_PROGRESS:
                    task.run()
            sleep(1)

class Task():
    """
    repeat days is a list of days of the week that the task should repeat
    """
    def __init__(self, id, name, description, duration, start_time, end_time, status, priority, repeat_days = [],  repeat_end_time = None, task_function = None):
        self.id = id
        self.name = name
        self.description = description
        self.duration = duration
        self.start_time = start_time
        self.end_time = end_time
        self.status = status
        self.priority = priority
        self.repeat_days = repeat_days
        self.repeat_end_time = repeat_end_time
        self.task_function = task_function

    def __str__(self):
        return f"Task: {self.name} - {self.description} - {self.duration} - {self.start_time} - {self.end_time} - {self.status} - {self.priority}"

    def run(self):
        PIHOME_LOGGER.info(f"Running Task: {self.name}")
        Thread(target=self.task_function, daemon=True).start()

class TaskPriority():
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class TaskStatus():
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


# Initialize the task manager
TASK_MANAGER = TaskManager()
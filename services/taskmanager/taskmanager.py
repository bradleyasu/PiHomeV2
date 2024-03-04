import atexit
from datetime import datetime, timedelta
from enum import Enum
import hashlib
import os
import pickle
from threading import Thread
from time import sleep
import uuid
from events.pihomeevent import PihomeEventFactory
from screens.Task.taskscreen import TaskScreen
from util.phlog import PIHOME_LOGGER

class TaskStatus(Enum):
    PENDING = 1
    PRE_IN_PROGRESS = 2
    IN_PROGRESS = 3
    COMPLETED = 4
    CANCELED = 5

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3

class TaskManager():
    task_store = "tasks.pihome"
    is_running = False
    task_screen = None
    thread = None

    def __init__(self):
        self.tasks = []
        atexit.register(self.serialize_tasks_on_exit)
        self.deserialize_tasks_on_start()

    def load_saved_tasks(self):
        """ 
        Saved tasks are stored in an ini file.  This method will load the saved tasks
        """
        # load task_store
        data = open(self.task_store, "r")
        # create tasks
        # add tasks to task list
        # close file
        data.close()


    def start(self, task_screen: TaskScreen):
        if not self.is_running:
            self.is_running = True
            self.task_screen = task_screen
            self.thread = Thread(target=self.run_service, daemon=True).start()
            PIHOME_LOGGER.info("Task Manager is has started")
        else:
            PIHOME_LOGGER.warn("Task Manager is already running")

    def stop(self):
        if self.is_running:
            self.is_running = False
            self.thread.join()
            PIHOME_LOGGER.info("Task Manager is has stopped")

    def restart(self):
        PIHOME_LOGGER.info("Task Manager is restarting")
        self.stop()
        self.start()

    def serialize_tasks(self, file_path = None):
        if file_path is None:
            file_path = self.task_store
        tasks = self.tasks

        # remove any task that isn't COMPLETED
        tasks = [task for task in tasks if task.status != TaskStatus.COMPLETED]

        # remove any task that is not cacheable
        tasks = [task for task in tasks if task.cacheable == True]

        with open(file_path, 'wb') as file:
            pickle.dump(tasks, file)
        
        PIHOME_LOGGER.info("Serialized {} tasks".format(len(tasks)))

    def deserialize_tasks(self, file_path = None):
        if file_path is None:
            file_path = self.task_store
        with open(file_path, 'rb') as file:
            self.tasks = pickle.load(file)

    
    def serialize_tasks_on_exit(self):
        # remove any tasks that are not pending
        self.serialize_tasks()


    def deserialize_tasks_on_start(self):
        # if the file exists, load the tasks
        if os.path.exists(self.task_store):
            self.deserialize_tasks(self.task_store)
            PIHOME_LOGGER.info("Task manager has loaded {} from {}".format(len(self.tasks), self.task_store))

    def add_task(self, task):
        PIHOME_LOGGER.info(f"Adding Task: {task.name}")
        # make sure task doesn't already exist
        for t in self.tasks:
            if t.hash == task.hash:
                PIHOME_LOGGER.warn(f"Task already exists: {task.name}")
                return

        self.tasks.append(task)
        self.serialize_tasks()

    def remove_task(self, task):
        PIHOME_LOGGER.info(f"Removing Task: {task.name}")
        self.tasks.remove(task)
        self.serialize_tasks()

    def remove_task_by_id(self, id):
        for task in self.tasks:
            if task.id == id:
                self.tasks.remove(task)
                return True
        return False

    def get_tasks(self):
        return self.tasks

    def get_task_by_id(self, id):
        for task in self.tasks:
            if task.id == id:
                return task
        return None

    def process_tasks(self):
        # if task screen is open, do not process tasks
        if self.task_screen.is_open:
            return
        for task in self.tasks:
            if task.status == TaskStatus.PENDING or task.status == TaskStatus.IN_PROGRESS:
                if task.start_time <= datetime.now():
                    task.status = TaskStatus.PRE_IN_PROGRESS
                    if not task.is_passive:
                        self.load_task_screen(task)
                    # We want to return so that we don't process any other tasks.  This will allow the task screen to be displayed and remaining tasks will be queued 
                    return 
    
    def load_task_screen(self, task):
        self.task_screen.set_task(task)
        self.task_screen.show()

    def ack_task(self, confirm = True):
        if self.task_screen is None or not self.task_screen.is_open:
            return None
        if confirm:
            self.task_screen.confirm()
        else:
            self.task_screen.cancel()
        return self.task_screen.task.id

    def run_service(self):
        while True:
            self.process_tasks()
            for task in self.tasks:
                if task.status == TaskStatus.PRE_IN_PROGRESS:
                    task.status = TaskStatus.IN_PROGRESS
                    task.run()
            sleep(1)

    def delete_task_cache(self):
        if os.path.exists(self.task_store):
            os.remove(self.task_store)
            PIHOME_LOGGER.info(f"Deleted task cache: {self.task_store}")

    def tasks_to_json(self):
        json_tasks = []
        for task in self.tasks:
            start_time_str = task.start_time.strftime("%Y-%m-%d %H:%M:%S")
            json_tasks.append({
                "id": task.id,
                "name": task.name,
                "description": task.description,
                "start_time": start_time_str,
                "status": task.status.name,
                "priority": task.priority.name
            })
        return json_tasks

class Task():
    """
    repeat days is a list of days of the week that the task should repeat
    """
    hash = None
    def __init__(self, name, description, start_time, status: TaskStatus, priority: TaskPriority, is_passive = False, repeat_days = 0, on_run = None, on_confirm = None, on_cancel = None, background_image = None, cacheable = True):
        # set id to random hash
        self.id = str(uuid.uuid4())
        self.name = name
        self.description = description
        self.start_time = start_time
        self.status = status
        self.priority = priority
        self.repeat_days = repeat_days
        self.on_run = on_run
        self.is_passive = is_passive
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel
        self.background_image = background_image
        self.cacheable = cacheable

        # create an md5 hash based on the task name, description, and start time
        self.hash = hashlib.md5(f"{self.name}{self.description}{self.start_time}".encode()).hexdigest()

    def __str__(self):
        return f"Task: {self.name} - {self.description} - {self.duration} - {self.start_time} - {self.end_time} - {self.status} - {self.priority}"

    def run(self):
        PIHOME_LOGGER.info(f"Running Task: {self.name}")
        self.schedule_next()
        try:
            if self.on_run is not None:
                PihomeEventFactory.create_event_from_dict(self.on_run).execute()
        except Exception as e:
            PIHOME_LOGGER.error(f"Failed to run task: {self.name} - {e}")

        # if the task is passive, mark it as completed after running
        if self.is_passive:
            self.status = TaskStatus.COMPLETED
        # non passive tasks are marked as completed or canceled by the user in the TaskScreen
    
    def schedule_next(self):
        if self.repeat_days > 0:
            # schedule the next task
            next_time = self.start_time + timedelta(days=self.repeat_days)
            TASK_MANAGER.add_task(Task(self.name, self.description, next_time, TaskStatus.PENDING, self.priority, self.is_passive, self.repeat_days, self.on_run, self.on_confirm, self.on_cancel))
            PIHOME_LOGGER.info(f"Scheduled next task: {self.name} for {next_time}")


# Initialize the task manager
TASK_MANAGER = TaskManager()
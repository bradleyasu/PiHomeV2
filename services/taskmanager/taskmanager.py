import atexit
from datetime import datetime, timedelta
from enum import Enum
import os
import pickle
from threading import Thread
from time import sleep
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
    task_store = "tasks.ini"
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

    def serialize_tasks(self, file_path):
        with open(file_path, 'wb') as file:
            pickle.dump(self.tasks, file)

    def deserialize_tasks(self, file_path):
        with open(file_path, 'rb') as file:
            self.tasks = pickle.load(file)
    
    def serialize_tasks_on_exit(self):
        # remove any tasks that are not pending
        self.tasks = [task for task in self.tasks if task.status == TaskStatus.PENDING]
        self.serialize_tasks(self.task_store)

    def deserialize_tasks_on_start(self):
        # if the file exists, load the tasks
        if os.path.exists(self.task_store):
            self.deserialize_tasks(self.task_store)
            PIHOME_LOGGER.info("Task manager has loaded {} from {}".format(len(self.tasks), self.task_store))

    def add_task(self, task):
        PIHOME_LOGGER.info(f"Adding Task: {task.name}")
        self.tasks.append(task)

    def remove_task(self, task):
        PIHOME_LOGGER.info(f"Removing Task: {task.name}")
        self.tasks.remove(task)

    def remove_task_by_id(self, id):
        for task in self.tasks:
            if task.id == id:
                self.tasks.remove(task)
                return
        return None

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
            if task.status == TaskStatus.PENDING:
                if task.start_time <= datetime.now():
                    task.status = TaskStatus.PRE_IN_PROGRESS
                    self.load_task_screen(task)
    
    def load_task_screen(self, task):
        self.task_screen.set_task(task)
        self.task_screen.show()

    def run_service(self):
        while True:
            self.process_tasks()
            for task in self.tasks:
                if task.status == TaskStatus.PRE_IN_PROGRESS:
                    task.status = TaskStatus.IN_PROGRESS
                    task.run()
            sleep(1)

class Task():
    """
    repeat days is a list of days of the week that the task should repeat
    """
    def __init__(self, name, description, start_time, status: TaskStatus, priority: TaskPriority, repeat_days = 0, task_function = None, on_confirm = None, on_cancel = None):
        # set id to random hash
        self.id = hash(name + description + str(datetime.now()))
        self.name = name
        self.description = description
        self.start_time = start_time
        self.status = status
        self.priority = priority
        self.repeat_days = repeat_days
        self.task_function = task_function
        self.on_confirm = on_confirm
        self.on_cancel = on_cancel

    def __str__(self):
        return f"Task: {self.name} - {self.description} - {self.duration} - {self.start_time} - {self.end_time} - {self.status} - {self.priority}"

    def run(self):
        PIHOME_LOGGER.info(f"Running Task: {self.name}")
        self.schedule_next()
        #### TODO SHOULD CUSTOM "EVENT" objects be passed instead of functions? #### 
        # Thread(target=lambda _: self.task_function(self, self.on_confirm, self.on_cancel), daemon=True).start()
        self.status = TaskStatus.COMPLETED
    
    def schedule_next(self):
        if self.repeat_days > 0:
            # schedule the next task
            next_time = self.start_time + timedelta(days=self.repeat_days)
            TASK_MANAGER.add_task(Task(self.name, self.description, next_time, TaskStatus.PENDING, self.priority, self.repeat_days, self.task_function, self.on_confirm, self.on_cancel))
            PIHOME_LOGGER.info(f"Scheduled next task: {self.name} for {next_time}")


# Initialize the task manager
TASK_MANAGER = TaskManager()
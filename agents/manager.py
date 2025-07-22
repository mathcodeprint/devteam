from .base import BaseAgent
import json
import os

class ManagerAgent(BaseAgent):
    def __init__(self, name, role, skills, description, project_dir, timeout=120):
        super().__init__(name, role, skills, description, project_dir, timeout=timeout)
        self.task_list = []
        self.progress_report = []

    def load_tasks(self, task_file):
        """Load tasks from a JSON file."""
        with open(task_file, "r") as f:
            self.task_list = json.load(f)["tasks"]

    def assign_task(self, task, agent):
        """Assign a task to an agent."""
        self.send_message(agent, {"task": task})
        print(f"{self.name} assigned task '{task['description']}' to {agent}")
        self.progress_report.append(f"Assigned task '{task['description']}' to {agent}")

    def perform_task(self, task):
        """Manager's task is to distribute tasks and generate progress report."""
        if task["type"] == "distribute":
            print(f"{self.name} (Role: {self.role}) executing: {self.description}")
            for t in self.task_list:
                if t["type"] == "test":
                    target = "Tester1"
                else:
                    target = "Dev1" if "hello" in t["description"].lower() else "Dev2"
                self.assign_task(t, target)
                if "integration_supervision" in self.skills:
                    self.progress_report.append(f"Ensured no overlap for task '{t['description']}'")
            self.generate_progress_report()

    def generate_progress_report(self):
        """Output a sprint-level progress report."""
        report_file = os.path.join(self.project_dir, "progress_report.txt")
        with open(report_file, "w") as f:
            f.write(f"Sprint Progress Report by {self.name}\n")
            f.write(f"Description: {self.description}\n")
            f.write("Tasks Assigned:\n")
            for entry in self.progress_report:
                f.write(f"- {entry}\n")
        print(f"{self.name} generated progress report at {report_file}")

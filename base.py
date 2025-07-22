import json
import os
from abc import ABC, abstractmethod
import glob2 as glob

class BaseAgent(ABC):
    def __init__(self, name, role, skills, description, project_dir):
        self.name = name
        self.role = role
        self.skills = skills
        self.description = description  # New field
        self.project_dir = project_dir
        self.comms_dir = os.path.join(project_dir, "comms")
        os.makedirs(self.comms_dir, exist_ok=True)

    def send_message(self, recipient, message):
        """Send a message to another agent via file-based queue, avoiding duplicates."""
        message_data = {"sender": self.name, "recipient": recipient, "message": message}
        message_file = os.path.join(self.comms_dir, f"msg_{recipient}_{self.name}.json")
        
        existing_messages = []
        if os.path.exists(message_file):
            with open(message_file, "r") as f:
                for line in f:
                    if line.strip():
                        existing_messages.append(json.loads(line.strip()))
        
        if message_data not in existing_messages:
            with open(message_file, "a") as f:
                json.dump(message_data, f)
                f.write("\n")

    def receive_messages(self):
        """Read messages intended for this agent and move them to a processed file."""
        messages = []
        message_file_pattern = os.path.join(self.comms_dir, f"msg_{self.name}_*.json")
        processed_dir = os.path.join(self.comms_dir, "processed")
        os.makedirs(processed_dir, exist_ok=True)

        for message_file in glob.glob(message_file_pattern):
            if os.path.exists(message_file):
                with open(message_file, "r") as f:
                    for line in f:
                        if line.strip():
                            messages.append(json.loads(line.strip()))
                
                processed_file = os.path.join(processed_dir, os.path.basename(message_file))
                os.rename(message_file, processed_file)

        return messages

    @abstractmethod
    def perform_task(self, task):
        pass

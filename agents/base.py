import json
import os
import glob2 as glob
from abc import ABC, abstractmethod
import requests

class BaseAgent(ABC):
    def __init__(self, name, role, skills, description, project_dir, timeout=120):
        self.name = name
        self.role = role
        self.skills = skills
        self.description = description
        self.project_dir = project_dir
        self.comms_dir = os.path.join(project_dir, "comms")
        os.makedirs(self.comms_dir, exist_ok=True)
        self.api_url = "http://localhost:11434/api/chat"
        self.timeout = timeout

    def call_local_model(self, prompt):
        """Call the local qwen3-custom model API with retries and robust error handling."""
        import time
        payload = {
            "model": "qwen3-custom",
            "messages": [{"role": "user", "content": f"{prompt} /think"}],
            "stream": False
        }
        retries = 0
        max_retries = 3
        backoff = 2

        url = "http://localhost:11434/api/generate"
        data = {
            "model": "qwen-custom",
            "prompt": prompt,
            "stream": False
           }
        if hasattr(self, 'use_gpu') and self.use_gpu:
            data["options"] = {
                "num_gpu": -1,  # Offload all layers to GPU
                "keep_alive": -1  # Keep model loaded indefinitely to avoid reload delays
            }
        else:
            data["options"] = {
                "keep_alive": -1  # Still useful for CPU to avoid unloading
            }


        while retries < max_retries:
            try:
                response = requests.post(self.api_url, json=payload, timeout=self.timeout)
                response.raise_for_status()
                return response.json()["message"]["content"]
            except requests.Timeout:
                print(f"{self.name} API call timed out after {self.timeout} seconds. Retrying ({retries+1}/{max_retries})...")
            except requests.ConnectionError as e:
                print(f"{self.name} API connection error: {e}. Retrying ({retries+1}/{max_retries})...")
            except requests.RequestException as e:
                print(f"{self.name} API call failed: {e}. Retrying ({retries+1}/{max_retries})...")
            time.sleep(backoff * (2 ** retries))
            retries += 1
        print(f"{self.name} failed to get a response from the local model after {max_retries} attempts.")
        return None

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

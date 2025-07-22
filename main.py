import json
import os
print("Current Working Directory:", os.getcwd())
from agents.manager import ManagerAgent
from agents.developer import DeveloperAgent
from agents.tester import TestingAgent
import queue
import sys
from io import StringIO
import subprocess
import time
import requests
from requests.exceptions import RequestException
try:
    import psutil
except ImportError:
    psutil = None

class StdoutQueue:
    """Redirect stdout to a queue for GUI display."""
    def __init__(self, output_queue):
        self.output_queue = output_queue
        self.buffer = StringIO()

    def write(self, text):
        self.buffer.write(text)
        self.output_queue.put(text)

    def flush(self):
        pass

def has_nvidia_gpu():
    try:
        subprocess.check_output(['nvidia-smi'])
        return True
    except Exception:
        return False

def has_amd_gpu():
    try:
        subprocess.check_output(['rocm-smi'])
        return True
    except Exception:
        return False    

def load_agents(config_file, project_dir):
    """Load agents from JSON configuration."""
    print(f"Loading agents from {config_file}")
    with open(config_file, "r") as f:
        config = json.load(f)
    
    agents = {}
    for agent_config in config["agents"]:
        agent_type = agent_config["type"]
        name = agent_config["name"]
        role = agent_config["role"]
        skills = agent_config["skills"]
        description = agent_config.get("description", "")
        print(f"Creating agent: {name} ({agent_type})")
        
        if agent_type == "manager":
            agents[name] = ManagerAgent(name, role, skills, description, project_dir)
        elif agent_type == "developer":
            specialization = agent_config.get("specialization", "")
            agents[name] = DeveloperAgent(name, role, skills, description, specialization, project_dir)
        elif agent_type == "tester":
            agents[name] = TestingAgent(name, role, skills, description, project_dir)
        else:
            print(f"Warning: Unknown agent type '{agent_type}' for agent '{name}'. Skipping.")
    
    return agents

def perform_task_with_retries(agent, task, max_retries=3, timeout=30, console_queue=None):
    """Perform a task with retries in case of API call failures."""
    retries = 0
    while retries < max_retries:
        try:
            if console_queue:
                agent.perform_task(task, console_queue=console_queue)
            else:
                agent.perform_task(task)
            return True  # Task succeeded
        except RequestException as e:
            retries += 1
            print(f"{agent.name} API call failed: {e}. Retrying ({retries}/{max_retries})...")
            time.sleep(60)  # Wait before retrying
    print(f"{agent.name} failed to complete task {task['id']} after {max_retries} retries.")
    return False

def main(output_queue=None, console_queue=None):
    """Main function with optional output and console queues for GUI."""
    # Check if qwen-custom Ollama instance is running
    def is_qwen_running():
        if psutil is None:
            return False  # psutil not available, can't check
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                if proc.info['name'] and 'ollama' in proc.info['name'].lower():
                    if proc.info['cmdline'] and any('qwen-custom' in str(arg) for arg in proc.info['cmdline']):
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return False

    if not is_qwen_running():
        print("Qwen-custom Ollama instance not running. Starting...")
        try:
            # Start ollama run qwen-custom in background
            subprocess.Popen(['ollama', 'run', 'qwen-custom'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            # Wait a bit for the server to start
            time.sleep(60)
            print("Qwen-custom Ollama instance started.")
        except Exception as e:
            print(f"Failed to start qwen-custom Ollama instance: {e}")
    else:
        print("Qwen-custom Ollama instance already running.")

    # Redirect stdout if queue is provided
    if output_queue:
        sys.stdout = StdoutQueue(output_queue)
    
    try:
        print("Starting main script")
        project_dir = os.path.join(os.getcwd(), "project")
        os.makedirs(project_dir, exist_ok=True)
        
        # Load agents
        config_file = "config/agents.json"
        agents = load_agents(config_file, project_dir)
        
        has_gpu = has_nvidia_gpu() or has_amd_gpu()
        for agent in agents.values():
            agent.use_gpu = has_gpu
        print(f"GPU detected: {has_gpu}. Ollama will attempt to use GPU if True.")

        # Example task file
        task_file = "config/tasks.json"
        print(f"Creating task file: {task_file}")
        with open(task_file, "w") as f:
            tasks = {
                "tasks": [
                    {
                        "id": 1,
                        "description": "Implement Hello function",
                        "type": "code",
                        "function_name": "hello",
                        "return_value": "Hello"
                    },
                    {
                        "id": 2,
                        "description": "Implement World function",
                        "type": "code",
                        "function_name": "world",
                        "return_value": "World"
                    },
                    {
                        "id": 3,
                        "description": "Test Hello World output",
                        "type": "test",
                        "test_spec": {
                            "combination": "print(hello() + ' ' + world())",
                            "expected_output": "Hello World"
                        }
                    }
                ]
            }
            json.dump(tasks, f)
        
        # Manager loads and distributes tasks
        print("Manager processing tasks")
        manager = agents["ProjectOrchestrator"]
        manager.load_tasks(task_file)
        manager.perform_task({"type": "distribute"})
        
        # Developers process assigned tasks
        print("Developers processing tasks")
        processed_tasks = {}
        for agent_name, agent in agents.items():
            if isinstance(agent, DeveloperAgent):
                processed_tasks[agent_name] = set()
                messages = agent.receive_messages()
                for msg in messages:
                    if "task" in msg["message"]:
                        task = msg["message"]["task"]
                        task_id = task["id"]
                        if task_id not in processed_tasks[agent_name]:
                            success = perform_task_with_retries(agent, task)
                            if success:
                                processed_tasks[agent_name].add(task_id)
        
        # Tester processes test task
        print("Tester processing tasks")
        tester = agents.get("Tester1")
        if tester:
            processed_tasks[tester.name] = set()
            messages = tester.receive_messages()
            for msg in messages:
                if "task" in msg["message"]:
                    task = msg["message"]["task"]
                    task_id = task["id"]
                    if task_id not in processed_tasks[tester.name]:
                        # Pass console_queue to perform_task if available
                        if console_queue:
                            success = perform_task_with_retries(tester, task, console_queue=console_queue)
                        else:
                            success = perform_task_with_retries(tester, task)
                        if success:
                            processed_tasks[tester.name].add(task_id)
    
    finally:
        # Restore stdout
        if output_queue:
            sys.stdout = sys.__stdout__

if __name__ == "__main__":
    main()

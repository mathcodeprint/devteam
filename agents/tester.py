from .base import BaseAgent
import os
import subprocess
import re

class TestingAgent(BaseAgent):
    def __init__(self, name, role, skills, description, project_dir, timeout=120):
        super().__init__(name, role, skills, description, project_dir, timeout=timeout)
        self.src_dir = os.path.join(project_dir, "src")
        self.test_dir = os.path.join(project_dir, "tests")
        os.makedirs(self.test_dir, exist_ok=True)

    def perform_task(self, task, console_queue=None):
        """Generate and run a test script using the local AI model. Output to console_queue if provided."""
        def send_console(msg):
            print(msg)
            if console_queue:
                console_queue.put(msg + '\n')
        send_console(f"{self.name} (Role: {self.role}) testing task: {task['description']} ({self.description})")
        
        # Collect developer code file names
        dev_files = [f for f in os.listdir(self.src_dir) if f.endswith('.py')]
        if not dev_files:
            send_console(f"{self.name} found no code to test")
            return

        prelude = (
           "import sys\n"
           "import os\n"
           "sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))\n"
        )
        import_lines = [f"from src.{os.path.splitext(f)[0]} import *" for f in dev_files]
        
        # Get test specification
        test_spec = task.get("test_spec", {})
        combination = test_spec.get("combination", "")
        expected_output = test_spec.get("expected_output", "")
        
        # Generate test code using the model
        prompt = (
            f"You are testing a Python program with the following files: {', '.join(dev_files)}.\n"
            f"The task is: {task['description']}.\n"
        )
        if combination:
            prompt += f"Use this test code: {combination}\n"
        else:
            prompt += "Generate a test script that imports the developer files and calls their functions to produce the expected output.\n"
        if expected_output:
            prompt += f"The expected output is: '{expected_output}'.\n"
        prompt += (
            "Provide only the test code to run the test, no explanations or comments."
        )
        
        test_code = self.call_local_model(prompt)
        if not test_code:
            send_console(f"{self.name} failed to generate test script")
            return
        
        # Filter out non-Python lines (keep only import statements, function calls, assignments, print statements)
        code_lines = []
        for line in test_code.splitlines():
            l = line.strip()
            if not l or l.startswith('#'):
                continue
            if re.match(r'^(import |from |print\(|[\w_]+ ?=|[\w_]+\()', l):
                code_lines.append(l)
        filtered_code = '\n'.join(code_lines)
        if not filtered_code:
            send_console(f"{self.name} test script did not contain valid Python code.")
            return

        combined_script = prelude + '\n'.join(import_lines) + '\n\n' + filtered_code

        # Compose the test script: import developer files, then run the test code
        import_lines = [f"from src.{os.path.splitext(f)[0]} import *" for f in dev_files]

        combined_script = prelude + '\n'.join(import_lines) + '\n\n' + filtered_code

        test_script_path = os.path.join(self.test_dir, "test_hello_world.py")
        with open(test_script_path, "w") as f:
            f.write(combined_script)
        
        # Run the test script
        try:
            result = subprocess.run(
                ["python", test_script_path],
                capture_output=True,
                text=True,
                check=True
            )
            output = result.stdout.strip()
            send_console(f"{self.name} test output: {output}")
            
            # Verify output
            if expected_output:
                if output == expected_output:
                    send_console(f"{self.name} test passed: Output matches '{expected_output}'")
                else:
                    send_console(f"{self.name} test failed: Expected '{expected_output}', got '{output}'")
            else:
                send_console(f"{self.name} test completed with output: {output}")
            
            # Save test result
            with open(os.path.join(self.test_dir, "test_result.txt"), "w") as f:
                f.write(f"Test Result by {self.name}\n")
                f.write(f"Output: {output}\n")
                f.write(f"Status: {'Passed' if output == expected_output else 'Failed' if expected_output else 'Completed'}\n")
        
        except subprocess.CalledProcessError as e:
            send_console(f"{self.name} test failed: Execution error - {e}")
            if e.stdout:
                send_console(f"Stdout:\n{e.stdout}")
            if e.stderr:
                send_console(f"Stderr:\n{e.stderr}")
            with open(os.path.join(self.test_dir, "test_result.txt"), "w") as f:
                f.write(f"Test Result by {self.name}\n")
                f.write(f"Error: {e}\n")
                f.write("Status: Failed\n")

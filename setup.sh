# Set project name
PROJECT_NAME="chatgpt_suite"

# Create project directory and subdirectories
mkdir -p $PROJECT_NAME/{agents,config,project/{src,comms}}

# Create empty __init__.py files to make agents a package
touch $PROJECT_NAME/agents/__init__.py

# Create empty main.py and requirements.txt
touch $PROJECT_NAME/main.py $PROJECT_NAME/requirements.txt

# Create virtual environment named after project
python3 -m venv $PROJECT_NAME/$PROJECT_NAME

# Activate virtual environment
source $PROJECT_NAME/$PROJECT_NAME/bin/activate

# Install requirements (glob2 as specified)
echo "glob2==0.7" > $PROJECT_NAME/requirements.txt
pip install -r $PROJECT_NAME/requirements.txt

# Deactivate virtual environment
deactivate

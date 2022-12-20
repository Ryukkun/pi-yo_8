import subprocess
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

try:
    subprocess.run(['pip','install','-r','requirements.txt'])
except Exception:
    subprocess.run(['pip3','install','-r','requirements.txt'])

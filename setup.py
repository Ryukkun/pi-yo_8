import subprocess

try:
    subprocess.run(['pip','install','-r','requirements.txt'])
except Exception:
    subprocess.run(['pip3','install','-r','requirements.txt'])
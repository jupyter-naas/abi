import glob

command = "dagster dev --host 0.0.0.0 --port 3000"

for df in glob.glob("src/**/orchestration/definitions.py", recursive=True):
    command += f" -m {df} ".replace('/', '.').replace('.py', '')
    
print(command)
import glob

command = "dagster dev --port 3000"

for df in glob.glob("src/**/orchestration/definitions.py", recursive=True):
    command += f" -m {df} ".replace('/', '.').replace('.py', '')
    
print(command)
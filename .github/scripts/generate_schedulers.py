import yaml, os
import pydash as _ 

template_str = """
name: CI/CD Workflow

on: {}

jobs:
  scheduler:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Log in to GitHub Container Registry
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Pull Docker image
        run: docker pull ghcr.io/jupyter-naas/abi/abi:latest

      # - name: Run Papermill
      #   run: |
      #     docker run --name abi-execution -i --platform linux/amd64 ghcr.io/jupyter-naas/abi/abi:latest ls
      #     mkdir output
      #     docker cp abi-execution:/app/__pipeline__.ipynb ./output/__pipeline__.ipynb

      # - name: Upload output artifacts
      #   uses: actions/upload-artifact@v4
      #   with:
      #     name: output-files
      #     path: ./output
"""

def generate_schedulers(config : dict, template : str):
  for scheduler in config["schedulers"]:
      # Skip disabled schedulers
      if scheduler.get("enabled", False) is False:
          continue

      # Load template
      cicd = yaml.safe_load(template_str)
      del cicd[True]
      print(cicd)

      _.set_(cicd, "name", f"Scheduler - {scheduler['name']}")

      cicd["on"] = {"schedule": [{"cron": scheduler["cron"]}], "workflow_dispatch": {}}


      new_step = {}
      
      new_step['name'] = scheduler['name']
      
      new_step['run'] = f"""
# Generate unique id
export SCHEDULER_ID=$(python -c "import uuid; print(uuid.uuid4())")

# Execute the Scheduler script
docker run --name $SCHEDULER_ID -i --platform linux/amd64 ghcr.io/jupyter-naas/abi/abi:latest python .github/scripts/run_scheduler.py "{scheduler['name']}"

# Create the output directory that will be used to store the output files and save them as artifacts.
mkdir -p outputs/

# Copy the output files from the container to the host.
docker cp $SCHEDULER_ID:/app/outputs ./outputs/

"""

      # Append the new step to the steps list
      cicd["jobs"]["scheduler"]["steps"].append(new_step)

      cicd["jobs"]["scheduler"]["steps"].append({
        'name': 'Upload output artifacts',
        'uses': 'actions/upload-artifact@v4',
        'with': {
          'name': 'output-files',
          'path': './outputs'
        }
      })

      # Write to file.
      # Make sure scheduler name is a valid filename.
      scheduler_name = scheduler["name"].replace(" ", "_").lower()
      yaml.dump(cicd, open(os.path.join('.github/workflows', f'scheduler__{scheduler_name}.yaml'), "w"))
    
if __name__ == "__main__":
  with open("config.yml", "r") as file:
    config = yaml.safe_load(file)
  
  generate_schedulers(config, template_str)
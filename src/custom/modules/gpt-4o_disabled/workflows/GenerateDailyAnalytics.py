from datetime import datetime
import schedule
import time
from pathlib import Path
import sys

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.append(str(project_root))

from src.custom.modules.gpt_4o_disabled.analytics.GeneratePyvis import generate_pyvis_network

def job():
    """Execute the Pyvis network generation job"""
    print(f"Running daily analytics job at {datetime.now()}")
    try:
        generate_pyvis_network()
        print("Successfully generated Pyvis network")
    except Exception as e:
        print(f"Error generating Pyvis network: {str(e)}")

def main():
    # Schedule the job to run at 9 AM every day
    schedule.every().day.at("09:00").do(job)
    
    print("Analytics scheduler started. Will run daily at 9:00 AM")
    
    # Keep the script running
    while True:
        schedule.run_pending()
        time.sleep(60)  # Check every minute

if __name__ == "__main__":
    main()

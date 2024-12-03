import os
import csv
from datetime import datetime
from typing import List, Dict
from pathlib import Path
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class TestReporter:
    def __init__(self):
        """Initialize the test reporter with required directories."""
        # Get project root directory
        self.project_root = Path(__file__).parent.parent
        
        # Set up paths relative to project root
        self.data_dir = self.project_root / "data" / "tests-data"
        self.analytics_dir = self.project_root / "analytics" / "reports" / "tests"
        
        logger.info(f"Project root: {self.project_root}")
        logger.info(f"Data directory: {self.data_dir}")
        logger.info(f"Analytics directory: {self.analytics_dir}")
        
        self.results = []
        self._ensure_dirs()
    
    def _ensure_dirs(self):
        """Create necessary directories if they don't exist."""
        try:
            # Create data/tests-data directory
            os.makedirs(self.data_dir, exist_ok=True)
            logger.info(f"Created/verified data directory: {self.data_dir}")
            
            # Update analytics path
            analytics_dir = self.project_root / "analytics" / "reports" / "tests"
            os.makedirs(analytics_dir, exist_ok=True)
            logger.info(f"Created/verified analytics directory: {analytics_dir}")
        except Exception as e:
            logger.error(f"Error creating directories: {str(e)}")
            raise
    
    def add_result(self, test_name: str, status: bool, message: str = "", duration: float = 0.0):
        """Add a test result to the report."""
        result = {
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%Y-%m-%d"),
            "test_name": test_name,
            "status": "PASS" if status else "FAIL",
            "message": message,
            "duration": f"{duration:.3f}s"
        }
        logger.debug(f"Adding test result: {result}")
        self.results.append(result)
    
    def save_report(self) -> str:
        """Save test results to CSV file."""
        if not self.results:
            logger.warning("No results to save")
            return ""
            
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = self.data_dir / f"test_report_{timestamp}.csv"
        logger.info(f"Saving report to: {filename}")
        
        fieldnames = ["timestamp", "date", "test_name", "status", "message", "duration"]
        
        try:
            with open(filename, "w", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(self.results)
            logger.info(f"Successfully saved report to: {filename}")
        except Exception as e:
            logger.error(f"Error saving report: {str(e)}")
            raise
        
        return str(filename)

def run_test():
    """Run a simple test to verify the reporter is working."""
    logger.info("Starting test run")
    
    try:
        reporter = TestReporter()
        
        # Add some test results
        logger.info("Adding test results")
        reporter.add_result("Sample Test 1", True, "Success!", 0.5)
        reporter.add_result("Sample Test 2", False, "Failed because of X", 1.2)
        reporter.add_result("Sample Test 3", True, "Another success", 0.3)
        
        # Save the report
        filename = reporter.save_report()
        logger.info(f"Test run completed. Report saved to: {filename}")
        
        # Verify file exists
        if os.path.exists(filename):
            logger.info("Report file successfully created")
            # Read and display the first few lines
            with open(filename, 'r') as f:
                logger.info("Report contents:")
                for i, line in enumerate(f):
                    if i < 5:  # Show first 5 lines
                        logger.info(line.strip())
        else:
            logger.error("Report file was not created!")
            
    except Exception as e:
        logger.error(f"Error in test run: {str(e)}", exc_info=True)
        raise

if __name__ == "__main__":
    run_test()
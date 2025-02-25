from dataclasses import dataclass
import time

@dataclass
class TestResult:
    passed: int
    total: int
    coverage: float

def run_mock_tests() -> TestResult:
    """Simulates running tests with a mock delay and results."""
    print("\nRunning tests...")
    
    # Simulate test execution with delays
    print("Running unit tests...")
    time.sleep(0.5)
    print("Running integration tests...")
    time.sleep(0.7)
    print("Calculating coverage...")
    time.sleep(0.3)
    
    # Mock results
    result = TestResult(
        passed=198,
        total=200,
        coverage=89.5
    )
    
    # Display results
    print("\nTest Results:")
    print(f"Tests: {result.passed}/{result.total} passed")
    print(f"Coverage: {result.coverage}%\n")
    
    return result 
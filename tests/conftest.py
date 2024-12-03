import pytest
import os
import sys
import tempfile

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Common fixtures can be added here
@pytest.fixture
def mock_perplexity_response():
    return {
        'choices': [{
            'message': {
                'content': 'Donald Trump won the 2024 US presidential election, defeating incumbent Joe Biden. Trump secured the electoral college victory after a contentious election season.'
            }
        }]
    }

@pytest.fixture
def sample_file():
    # Create a temporary file with some content
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        f.write("This is a test content\nLine 2\nLine 3")
        temp_file_path = f.name
    
    yield temp_file_path
    
    # Cleanup after test
    os.unlink(temp_file_path) 
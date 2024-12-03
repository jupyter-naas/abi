import pytest
import os

def read_file(file_path):
    with open(file_path, 'r') as f:
        return f.read()

@pytest.fixture
def sample_file(tmp_path):
    # Create a temporary file with test content
    file_path = tmp_path / "test_file.txt"
    with open(file_path, 'w') as f:
        f.write("This is a test content\nLine 2\nLine 3")
    return str(file_path)

def test_read_file(sample_file):
    # Read the content
    content = read_file(sample_file)
    
    # Assertions
    assert isinstance(content, str)
    assert len(content) > 0
    assert "This is a test content" in content
    assert content.count('\n') == 2  # Checking for 3 lines
    
def test_file_not_found():
    with pytest.raises(FileNotFoundError):
        read_file("nonexistent_file.txt") 
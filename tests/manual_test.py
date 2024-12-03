from workflows.functions import handle_function_calls, get_function_definitions
from integrations.tools import generate_image, read_file, write_file, send_message
import json

def test_write_and_read():
    print("\nTesting file operations...")
    
    # Test write
    write_result = write_file("test.txt", "Hello from migration test!")
    print(f"Write result: {write_result}")
    
    # Test read
    read_result = read_file("test.txt")
    print(f"Read result: {read_result}")
    
    assert "Hello from migration test!" in read_result, "File content mismatch"
    print("✅ File operations test passed")

def test_function_definitions():
    print("\nTesting function definitions...")
    
    definitions = get_function_definitions()
    print(f"Found {len(definitions)} function definitions")
    
    # Print available functions
    for func in definitions:
        print(f"- {func['function']['name']}")
    
    print("✅ Function definitions test passed")

def test_twilio():
    print("\nTesting Twilio messaging...")
    
    # Test SMS
    sms_result = send_message(
        to="+33685256997",
        message="Test message from ABI Twilio integration"
    )
    print(f"SMS result: {sms_result}")
    
    # Test MMS
    mms_result = send_message(
        to="+1234567890",
        message="Test MMS message",
        media_url="https://example.com/image.jpg"
    )
    print(f"MMS result: {mms_result}")
    
    print("✅ Twilio tests completed")

def main():
    print("Starting migration validation tests...")
    
    try:
        test_write_and_read()
        test_function_definitions()
        test_twilio()
        
        print("\n✅ All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")

if __name__ == "__main__":
    main() 
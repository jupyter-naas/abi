#!/usr/bin/env python3
"""
File System Tools Example

This example demonstrates practical usage of ABI File System Tools
in real-world scenarios.
"""

import sys
from pathlib import Path

# Add the lib directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from abi.services.agent.tools import FileSystemTools, config_manager, FileSystemConfig, FileSystemPermissions

def document_management_example():
    """Example: Document management workflow."""
    print("📄 Document Management Example")
    print("=" * 40)
    
    # Initialize tools with development configuration
    tools = FileSystemTools(config_name="development")
    
    # Create project structure
    project_dir = "examples/project_docs"
    
    try:
        # Create project directory
        tools.create_directory(project_dir)
        print(f"✅ Created project directory: {project_dir}")
        
        # Create various document types
        documents = {
            "README.md": "# Project Documentation\n\nThis is a sample project with comprehensive documentation.",
            "config.json": '{"project": "ABI File System Demo", "version": "1.0.0", "author": "ABI Team"}',
            "requirements.txt": "abi-tools>=1.0.0\nlangchain>=0.1.0\npydantic>=2.0.0",
            "notes.txt": "Important project notes:\n- File system tools working well\n- Security features implemented\n- Ready for production use"
        }
        
        # Write documents
        for filename, content in documents.items():
            filepath = f"{project_dir}/{filename}"
            tools.write_file(filepath, content)
            print(f"✅ Created: {filename}")
        
        # List all documents
        listing = tools.list_directory(project_dir)
        print(f"\n📋 Project contents ({listing['total_items']} files):")
        for item in listing['items']:
            info = tools.get_file_info(item['path'])
            print(f"   - {item['name']} ({info['size']} bytes, {info['mime_type']})")
        
        # Search for specific files
        md_files = tools.search_files(project_dir, "*.md")
        print(f"\n🔍 Found {len(md_files)} markdown files:")
        for file in md_files:
            print(f"   - {file['name']}")
        
        # Create backup
        backup_dir = f"{project_dir}/backup"
        tools.create_directory(backup_dir)
        
        # Copy all files to backup
        for item in listing['items']:
            if item['type'] == 'file':
                source = item['path']
                destination = f"{backup_dir}/{item['name']}"
                tools.copy_file(source, destination)
                print(f"✅ Backed up: {item['name']}")
        
        # Read and display a document
        readme_content = tools.read_file(f"{project_dir}/README.md")
        print(f"\n📖 README.md content:\n{readme_content}")
        
        print("\n🎉 Document management example completed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def data_processing_example():
    """Example: Data processing workflow."""
    print("\n📊 Data Processing Example")
    print("=" * 40)
    
    # Initialize tools with production-like configuration
    prod_config = FileSystemConfig(
        base_path="examples/data_processing",
        permissions=FileSystemPermissions(
            can_read=True,
            can_write=True,
            can_delete=False,  # No deletion in production
            can_create_directories=True,
            can_move_files=False,
            can_copy_files=True,
            max_file_size=1024 * 1024,  # 1MB limit
            allowed_extensions={'.csv', '.json', '.txt', '.log'}
        )
    )
    
    config_manager.register_config("data_processing", prod_config)
    tools = FileSystemTools(config_name="data_processing")
    
    try:
        # Create data processing structure
        tools.create_directory("raw_data")
        tools.create_directory("processed_data")
        tools.create_directory("logs")
        
        # Generate sample CSV data
        csv_data = """id,name,value,timestamp
1,Product A,100.50,2024-01-01
2,Product B,200.75,2024-01-02
3,Product C,150.25,2024-01-03
4,Product D,300.00,2024-01-04
5,Product E,175.80,2024-01-05"""
        
        tools.write_file("raw_data/sales_data.csv", csv_data)
        print("✅ Created sample CSV data")
        
        # Generate sample JSON data
        json_data = """{
  "metadata": {
    "source": "sales_system",
    "date_range": "2024-01-01 to 2024-01-05",
    "total_records": 5
  },
  "summary": {
    "total_value": 927.30,
    "average_value": 185.46,
    "highest_value": 300.00
  }
}"""
        
        tools.write_file("processed_data/sales_summary.json", json_data)
        print("✅ Created processed JSON summary")
        
        # Create log file
        log_data = """[2024-01-01 10:00:00] INFO: Data processing started
[2024-01-01 10:00:05] INFO: Raw data loaded successfully
[2024-01-01 10:00:10] INFO: Data validation completed
[2024-01-01 10:00:15] INFO: Summary statistics calculated
[2024-01-01 10:00:20] INFO: Output files generated
[2024-01-01 10:00:25] INFO: Data processing completed successfully"""
        
        tools.write_file("logs/processing.log", log_data)
        print("✅ Created processing log")
        
        # List all processing directories
        for dir_name in ["raw_data", "processed_data", "logs"]:
            listing = tools.list_directory(dir_name)
            print(f"\n📁 {dir_name} ({listing['total_items']} files):")
            for item in listing['items']:
                info = tools.get_file_info(item['path'])
                print(f"   - {item['name']} ({info['size']} bytes)")
        
        # Demonstrate file operations
        print("\n🔄 File operations demonstration:")
        
        # Copy raw data to processed
        tools.copy_file("raw_data/sales_data.csv", "processed_data/sales_data_processed.csv")
        print("✅ Copied sales data to processed directory")
        
        # Search for all data files
        data_files = tools.search_files(".", "*.csv")
        data_files.extend(tools.search_files(".", "*.json"))
        print(f"\n🔍 Found {len(data_files)} data files:")
        for file in data_files:
            print(f"   - {file['path']} ({file['size']} bytes)")
        
        print("\n🎉 Data processing example completed!")
        
    except Exception as e:
        print(f"❌ Error: {e}")

def security_demo():
    """Example: Security features demonstration."""
    print("\n🔒 Security Features Demo")
    print("=" * 40)
    
    # Test different security configurations
    configs = {
        "restricted": FileSystemTools(config_name="restricted"),
        "production": FileSystemTools(config_name="production"),
        "development": FileSystemTools(config_name="development")
    }
    
    for config_name, tools in configs.items():
        print(f"\n🔧 Testing {config_name} configuration:")
        
        # Test permissions
        permissions = tools.config.get_allowed_operations()
        print(f"   Permissions: {permissions}")
        
        # Test file size limit
        print(f"   Max file size: {tools.config.permissions.max_file_size} bytes")
        
        # Test allowed extensions
        print(f"   Allowed extensions: {list(tools.config.permissions.allowed_extensions)[:5]}...")
        
        # Test path restrictions
        if tools.config.permissions.allowed_paths:
            print(f"   Allowed paths: {tools.config.permissions.allowed_paths}")
        else:
            print(f"   Allowed paths: All (except blocked)")
    
    print("\n🎉 Security demo completed!")

def cleanup():
    """Clean up example files."""
    print("\n🧹 Cleaning up example files...")
    
    try:
        import shutil
        
        # Remove example directories
        for dir_path in ["examples/project_docs", "examples/data_processing"]:
            if Path(dir_path).exists():
                shutil.rmtree(dir_path)
                print(f"✅ Removed: {dir_path}")
        
        # Remove test files
        for file_path in ["test_production.txt", "large_file.txt"]:
            if Path(file_path).exists():
                Path(file_path).unlink()
                print(f"✅ Removed: {file_path}")
        
        print("✅ Cleanup completed!")
        
    except Exception as e:
        print(f"⚠️ Cleanup warning: {e}")

if __name__ == "__main__":
    print("🚀 ABI File System Tools - Practical Examples")
    print("=" * 50)
    
    # Run examples
    document_management_example()
    data_processing_example()
    security_demo()
    
    # Cleanup
    cleanup()
    
    print("\n✨ All examples completed!")
    print("\nKey takeaways:")
    print("- File system tools provide secure, configurable file access")
    print("- Different configurations for different environments")
    print("- Comprehensive permission and security controls")
    print("- Easy integration with ABI agents")

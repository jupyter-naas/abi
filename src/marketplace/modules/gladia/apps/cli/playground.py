#!/usr/bin/env python3
"""
Gladia CLI - Simple transcription tool
"""

import sys
import os
import argparse
import time

# Add project paths for imports
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.join(current_dir, '../../../../..')
src_path = os.path.join(project_root, 'src')
lib_path = os.path.join(project_root, 'lib')

if src_path not in sys.path:
    sys.path.insert(0, src_path)
if lib_path not in sys.path:
    sys.path.insert(0, lib_path)

class GladiaCLI:
    """Simple CLI for Gladia transcription."""
    
    def __init__(self):
        self.api_key = os.getenv('GLADIA_API_KEY')
        if not self.api_key:
            print("❌ GLADIA_API_KEY not found")
            print("Set: export GLADIA_API_KEY=your_key")
            sys.exit(1)
        
        # Import after path setup
        try:
            from marketplace.modules.gladia.integrations.GladiaIntegration import (
                GladiaIntegration, 
                GladiaIntegrationConfiguration
            )
            self.config = GladiaIntegrationConfiguration(api_key=self.api_key)
            self.client = GladiaIntegration(self.config)
        except ImportError as e:
            print(f"❌ Import error: {e}")
            print("Make sure you're running from the project root")
            sys.exit(1)
        
    def transcribe(self, url: str, language: str = "auto"):
        """Transcribe audio/video URL."""
        print(f"🎵 Transcribing: {url}")
        
        try:
            job = self.client.transcribe_audio_async(
                audio_url=url,
                language=language if language != "auto" else None
            )
            print(f"✅ Job ID: {job.job_id}")
            
            # Wait for completion
            print("⏳ Processing...")
            while True:
                status = self.client.get_transcription_status(job.job_id)
                
                if status.status == "done":
                    result = self.client.get_transcription_result(status.result_url)
                    print(f"\n📝 TRANSCRIPT:")
                    print("-" * 40)
                    print(result.full_transcript)
                    print(f"\n✅ Done! Confidence: {result.confidence:.1%}")
                    break
                elif status.status == "error":
                    print("❌ Failed")
                    break
                
                time.sleep(5)
                
        except Exception as e:
            print(f"❌ Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="Gladia CLI Transcription")
    parser.add_argument('url', help='Audio/video URL to transcribe')
    parser.add_argument('--language', '-l', default='auto', help='Language code')
    
    args = parser.parse_args()
    
    cli = GladiaCLI()
    cli.transcribe(args.url, args.language)

if __name__ == "__main__":
    print("🎤 Gladia CLI")
    main()
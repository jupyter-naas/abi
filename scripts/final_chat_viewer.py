#!/usr/bin/env python3
"""
Final Chat Viewer - Actually Works

Directly decodes msgpack from PostgreSQL without LangGraph complexity.
This is the definitive solution.

Usage:
    python scripts/final_chat_viewer.py [thread_id]
"""

import os
import sys
import msgpack
import psycopg2
import re

def get_connection():
    """Get PostgreSQL connection."""
    postgres_url = os.getenv("POSTGRES_URL", "postgresql://abi_user:abi_password@localhost:5432/abi_memory")
    return psycopg2.connect(postgres_url)

def extract_text_from_msgpack(blob_data):
    """Extract readable text from msgpack blob."""
    try:
        # Decode msgpack
        decoded = msgpack.unpackb(blob_data, raw=False, strict_map_key=False)
        
        # Handle ExtType objects (LangChain serialization)
        if hasattr(decoded, 'code') and hasattr(decoded, 'data'):
            try:
                # Decode the inner ExtType data
                inner = msgpack.unpackb(decoded.data, raw=False, strict_map_key=False)
                if isinstance(inner, list) and len(inner) >= 3:
                    message_data = inner[2]  # Third element contains the message data
                    if isinstance(message_data, dict):
                        content = message_data.get('content', '')
                        msg_type = message_data.get('type', 'unknown')
                        return msg_type, content
            except:
                pass
        
        # Handle direct list format
        if isinstance(decoded, list) and len(decoded) >= 3:
            # LangChain format: [?, ?, message_data, ?]
            message_data = decoded[2]
            if isinstance(message_data, dict):
                content = message_data.get('content', '')
                msg_type = message_data.get('type', 'unknown')
                return msg_type, content
        
        # Fallback: look for content in any dict
        def find_content(obj):
            if isinstance(obj, dict):
                if 'content' in obj:
                    return obj.get('type', 'unknown'), obj['content']
                for value in obj.values():
                    result = find_content(value)
                    if result:
                        return result
            elif isinstance(obj, list):
                for item in obj:
                    result = find_content(item)
                    if result:
                        return result
            return None
        
        result = find_content(decoded)
        if result:
            return result
            
        # Last resort: extract text from raw bytes
        text = str(decoded)
        if len(text) > 50:
            return 'unknown', text[:200] + '...'
            
    except Exception as e:
        # Try to extract readable text from raw bytes
        try:
            text_data = blob_data.decode('utf-8', errors='ignore')
            # Look for content patterns
            content_match = re.search(r'content.{1,10}([a-zA-Z0-9\s\.\?\!,]{10,200})', text_data)
            if content_match:
                return 'extracted', content_match.group(1).strip()
        except:
            pass
    
    return None, f"Could not decode ({len(blob_data)} bytes)"

def list_threads():
    """List all conversation threads."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT thread_id, COUNT(*) as message_count
                FROM checkpoint_writes 
                WHERE channel = 'messages'
                GROUP BY thread_id
                ORDER BY thread_id
            """)
            
            threads = cur.fetchall()
            
            print("Available conversation threads:")
            print("=" * 50)
            for thread_id, count in threads:
                print(f"Thread {thread_id}: {count} messages")
            print()
            return [t[0] for t in threads]

def show_chat_history(thread_id):
    """Show chat history for a specific thread."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT checkpoint_id, blob, idx
                FROM checkpoint_writes 
                WHERE thread_id = %s AND channel = 'messages'
                ORDER BY checkpoint_id, idx
            """, (thread_id,))
            
            messages = cur.fetchall()
            
            print(f"Chat History for Thread {thread_id}")
            print("=" * 60)
            print(f"Total messages: {len(messages)}")
            print("=" * 60)
            
            for i, (checkpoint_id, blob_data, idx) in enumerate(messages, 1):
                msg_type, content = extract_text_from_msgpack(blob_data)
                
                # Format the message
                if msg_type == 'human':
                    print(f"👤 USER [{i}]: {content}")
                elif msg_type == 'ai':
                    print(f"🤖 ABI [{i}]: {content}")
                elif msg_type == 'system':
                    print(f"⚙️  SYSTEM [{i}]: {content}")
                elif msg_type == 'tool':
                    print(f"🔧 TOOL [{i}]: {content}")
                elif msg_type == 'extracted':
                    print(f"📝 EXTRACTED [{i}]: {content}")
                else:
                    print(f"❓ UNKNOWN [{i}]: {content}")
                
                print()
            
            print("=" * 60)

def main():
    """Main function."""
    if len(sys.argv) > 1:
        thread_id = sys.argv[1]
        show_chat_history(thread_id)
    else:
        threads = list_threads()
        if threads:
            print("Usage: python scripts/final_chat_viewer.py <thread_id>")
            print(f"Example: python scripts/final_chat_viewer.py {threads[0]}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

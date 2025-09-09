#!/usr/bin/env python3
"""
Clean CLI for Naas GPT-4 - Consolidates all working code
"""

import click
import json
import sys
from pathlib import Path

# Add module path
module_path = Path(__file__).parent.parent
sys.path.insert(0, str(module_path))

from agents.NaasGPT4Agent import NaasGPT4Agent

@click.group()
def cli():
    """Naas GPT-4 CLI - Working implementation"""
    pass

@cli.command()
def run():
    """Start chat with GPT-4"""
    try:
        agent = NaasGPT4Agent()
        click.echo("🤖 Naas GPT-4 Chat")
        click.echo("Type 'quit' to exit")
        click.echo("-" * 30)
        
        while True:
            try:
                message = click.prompt("You", type=str)
                
                if message.lower() in ['quit', 'exit', 'bye']:
                    click.echo("Goodbye! 👋")
                    break
                
                result = agent.chat(message)
                
                if result["success"]:
                    click.echo(f"naas-openai-gpt4: {result['content']}")
                else:
                    click.echo(f"Error: {result['error']}", err=True)
                    
            except KeyboardInterrupt:
                click.echo("\\nGoodbye! 👋")
                break
                
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
@click.argument('message')
@click.option('--json', '-j', is_flag=True, help='JSON output')
def chat(message, json):
    """Send single message to GPT-4"""
    try:
        agent = NaasGPT4Agent()
        result = agent.chat(message)
        
        if json:
            click.echo(json.dumps(result, indent=2))
        else:
            if result["success"]:
                click.echo(f"GPT-4: {result['content']}")
                tokens = result.get('tokens', {})
                if tokens.get('input') or tokens.get('output'):
                    click.echo(f"Tokens: {tokens.get('input', 0)} → {tokens.get('output', 0)}")
            else:
                click.echo(f"Error: {result['error']}", err=True)
                
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
def interactive():
    """Interactive chat session"""
    try:
        agent = NaasGPT4Agent()
        click.echo("🤖 Naas GPT-4 Interactive Chat")
        click.echo("Commands: 'clear' (reset), 'quit' (exit)")
        click.echo("-" * 50)
        
        while True:
            try:
                message = click.prompt("You", type=str)
                
                if message.lower() in ['quit', 'exit', 'bye']:
                    click.echo("Goodbye! 👋")
                    break
                    
                if message.lower() == 'clear':
                    agent.clear_conversation()
                    click.echo("Conversation cleared.")
                    continue
                
                if message.lower() == 'summary':
                    summary = agent.get_conversation_summary()
                    click.echo(f"Messages: {summary['message_count']}")
                    continue
                
                result = agent.chat(message)
                
                if result["success"]:
                    click.echo(f"GPT-4: {result['content']}")
                    tokens = result.get('tokens', {})
                    if tokens.get('input') or tokens.get('output'):
                        click.echo(f"💡 {tokens.get('input', 0)} → {tokens.get('output', 0)} tokens")
                else:
                    click.echo(f"Error: {result['error']}", err=True)
                    
            except KeyboardInterrupt:
                click.echo("\\nGoodbye! 👋")
                break
                
    except Exception as e:
        click.echo(f"Error: {str(e)}", err=True)
        sys.exit(1)

@cli.command()
def test():
    """Test connection to Naas API"""
    try:
        agent = NaasGPT4Agent()
        result = agent.chat("test connection")
        
        if result["success"]:
            click.echo("✅ Connection OK")
            tokens = result.get('tokens', {})
            click.echo(f"Test tokens: {tokens.get('input', 0)} → {tokens.get('output', 0)}")
        else:
            click.echo("❌ Connection Failed")
            click.echo(f"Error: {result['error']}")
            
    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)

if __name__ == '__main__':
    cli()
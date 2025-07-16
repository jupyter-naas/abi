#!/usr/bin/env python3
"""
Message Simulation CLI

Generates realistic message exchange simulations between humans and AI agents
using OpenAI's capabilities. Stores results in structured markdown files.
"""

import argparse
import csv
import json
import os
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from openai import OpenAI

# Import the project's secret system
sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))
from src import secret


class MessageSimulator:
    """Generates realistic message conversations using OpenAI."""
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize the simulator with OpenAI API key."""
        # Use project's secret system or fallback to provided key
        openai_key = api_key or secret.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key=openai_key)
        self.simulation_dir = Path(__file__).parent / "message_simulations"
        self.simulation_dir.mkdir(exist_ok=True)
        
        # Conversation templates and scenarios
        self.conversation_scenarios = [
            "customer_support", "technical_assistance", "educational_tutoring",
            "creative_collaboration", "problem_solving", "casual_chat",
            "professional_consultation", "debugging_session", "brainstorming",
            "interview", "negotiation", "therapy_session", "research_discussion"
        ]
        
        self.participant_types = {
            "human": ["Alex", "Sam", "Jordan", "Casey", "Morgan", "Taylor", "Riley", "Cameron"],
            "ai": ["Assistant", "Helper", "Bot", "AI-Agent", "Advisor", "Companion", "Specialist"]
        }
    
    def ask_configuration_questions(self) -> Dict[str, str]:
        """Ask user 5 configuration questions for the simulation."""
        print("\n🤖 Message Simulation Configuration")
        print("=" * 50)
        
        questions = [
            {
                "key": "topic",
                "prompt": "What topic/domain should the conversation focus on?",
                "suggestion": "e.g., technology, business, education, health, entertainment"
            },
            {
                "key": "scenario_type",
                "prompt": f"What type of interaction scenario? ({', '.join(self.conversation_scenarios[:5])}...)",
                "suggestion": f"Available: {', '.join(self.conversation_scenarios)}"
            },
            {
                "key": "participants",
                "prompt": "How many participants? (format: 'H humans, A ai_agents')",
                "suggestion": "e.g., '2 humans, 1 ai_agent' or '1 human, 2 ai_agents'"
            },
            {
                "key": "complexity",
                "prompt": "Conversation complexity level?",
                "suggestion": "simple, moderate, complex, highly_technical"
            },
            {
                "key": "special_context",
                "prompt": "Any special context or constraints?",
                "suggestion": "e.g., 'emergency situation', 'multilingual', 'technical jargon', 'casual tone'"
            }
        ]
        
        config = {}
        for i, question in enumerate(questions, 1):
            print(f"\n{i}/5: {question['prompt']}")
            print(f"   💡 {question['suggestion']}")
            
            while True:
                response = input("   ➤ ").strip()
                if response:
                    config[question['key']] = response
                    break
                print("   ⚠️  Please provide an answer.")
        
        return config
    
    def parse_participants(self, participants_str: str) -> Tuple[int, int]:
        """Parse participant string into human and AI counts."""
        try:
            # Parse formats like "2 humans, 1 ai_agent" or "1h, 2ai"
            parts = participants_str.lower().replace(",", " ").split()
            humans = 1
            ais = 1
            
            for i, part in enumerate(parts):
                if 'human' in part or part.endswith('h'):
                    # Look for number before this part
                    if i > 0 and parts[i-1].isdigit():
                        humans = int(parts[i-1])
                    elif part[0].isdigit():
                        humans = int(part[0])
                elif 'ai' in part or 'bot' in part:
                    # Look for number before this part
                    if i > 0 and parts[i-1].isdigit():
                        ais = int(parts[i-1])
                    elif part[0].isdigit():
                        ais = int(part[0])
            
            return min(humans, 4), min(ais, 4)  # Cap at 4 each for manageability
        except (ValueError, IndexError, AttributeError):
            return 1, 1  # Default fallback
    
    def generate_participants(self, num_humans: int, num_ais: int) -> List[Dict[str, str]]:
        """Generate participant profiles."""
        participants = []
        
        # Add humans
        human_names = random.sample(self.participant_types["human"], min(num_humans, len(self.participant_types["human"])))
        for name in human_names:
            participants.append({
                "name": name,
                "type": "human",
                "role": random.choice(["user", "expert", "learner", "client", "colleague"])
            })
        
        # Add AIs
        ai_names = random.sample(self.participant_types["ai"], min(num_ais, len(self.participant_types["ai"])))
        for name in ai_names:
            participants.append({
                "name": name,
                "type": "ai_agent",
                "role": random.choice(["assistant", "specialist", "tutor", "advisor", "facilitator"])
            })
        
        return participants
    
    def create_simulation_prompt(self, config: Dict[str, str], participants: List[Dict[str, str]]) -> str:
        """Create a detailed prompt for OpenAI to generate the conversation."""
        num_messages = random.randint(30, 50)
        
        participant_descriptions = []
        for p in participants:
            participant_descriptions.append(f"- {p['name']} ({p['type']}, {p['role']})")
        
        prompt = f"""Generate a realistic {num_messages}-message conversation about {config['topic']} in a {config['scenario_type']} scenario.

PARTICIPANTS:
{chr(10).join(participant_descriptions)}

CONTEXT:
- Topic: {config['topic']}
- Scenario: {config['scenario_type']}
- Complexity: {config['complexity']}
- Special context: {config['special_context']}

INSTRUCTIONS:
1. Create natural, flowing dialogue that feels authentic
2. Each message should be 1-3 sentences (some can be longer for complex topics)
3. Include realistic conversational elements: questions, clarifications, agreements, disagreements
4. AI agents should sound helpful but distinct from humans
5. Humans should sound natural with varied communication styles
6. Include some messages that are brief responses, others that are detailed
7. Show realistic conversation flow with topic evolution
8. Include occasional tangents, corrections, or clarifications
9. Make it feel like a real conversation with personality differences

FORMAT REQUIREMENT:
Return ONLY a JSON array where each message has this exact structure:
[
  {{
    "message_id": 1,
    "sender": "participant_name",
    "sender_type": "human|ai_agent",
    "timestamp_offset": "00:00:05",
    "content": "The actual message content here",
    "message_type": "text|question|answer|clarification|tangent"
  }}
]

Start with message_id 1 and increment. Use realistic timing (timestamp_offset from conversation start).
Generate exactly {num_messages} messages. Make it engaging and realistic!"""

        return prompt
    
    def generate_conversation(self, config: Dict[str, str], participants: List[Dict[str, str]]) -> List[Dict]:
        """Generate the conversation using OpenAI."""
        print("\n🔄 Generating conversation with OpenAI...")
        
        prompt = self.create_simulation_prompt(config, participants)
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",  # Use GPT-4 for higher quality
                messages=[
                    {
                        "role": "system", 
                        "content": "You are an expert conversation simulator. Generate realistic, engaging dialogues that feel natural and authentic. Follow the JSON format exactly."
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.8,  # Higher temperature for more creative/varied responses
                max_tokens=4000
            )
            
            content = response.choices[0].message.content
            if content is None:
                raise ValueError("Empty response from OpenAI")
            content = content.strip()
            
            # Try to parse JSON from the response
            if content.startswith("```json"):
                content = content.replace("```json", "").replace("```", "").strip()
            elif content.startswith("```"):
                content = content.replace("```", "").strip()
            
            messages = json.loads(content)
            
            if not isinstance(messages, list):
                raise ValueError("Response is not a list of messages")
            
            print(f"✅ Generated {len(messages)} messages successfully!")
            return messages
            
        except json.JSONDecodeError as e:
            print(f"❌ Failed to parse OpenAI response as JSON: {e}")
            return self._generate_fallback_conversation(participants)
        except Exception as e:
            print(f"❌ Error generating conversation: {e}")
            return self._generate_fallback_conversation(participants)
    
    def _generate_fallback_conversation(self, participants: List[Dict[str, str]]) -> List[Dict]:
        """Generate a simple fallback conversation if OpenAI fails."""
        print("🔄 Generating fallback conversation...")
        
        messages = []
        human_participants = [p for p in participants if p['type'] == 'human']
        ai_participants = [p for p in participants if p['type'] == 'ai_agent']
        
        # Simple back-and-forth pattern
        for i in range(35):  # Generate 35 messages
            if i % 2 == 0 and human_participants:
                sender = random.choice(human_participants)
                content = f"This is message {i+1} from {sender['name']} (human)"
            elif ai_participants:
                sender = random.choice(ai_participants)
                content = f"This is response {i+1} from {sender['name']} (AI agent)"
            else:
                sender = participants[0]
                content = f"This is message {i+1} from {sender['name']}"
            
            messages.append({
                "message_id": i + 1,
                "sender": sender['name'],
                "sender_type": sender['type'],
                "timestamp_offset": f"00:{i//2:02d}:{(i*15) % 60:02d}",
                "content": content,
                "message_type": "text"
            })
        
        return messages
    
    def save_simulation(self, config: Dict[str, str], participants: List[Dict[str, str]], 
                       messages: List[Dict]) -> str:
        """Save the simulation to a markdown file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        topic_clean = config['topic'].replace(" ", "_").replace("/", "_").lower()[:20]
        filename = f"{timestamp}_{topic_clean}.md"
        filepath = self.simulation_dir / filename
        
        # Calculate statistics
        human_messages = len([m for m in messages if m['sender_type'] == 'human'])
        ai_messages = len([m for m in messages if m['sender_type'] == 'ai_agent'])
        avg_length = sum(len(m['content']) for m in messages) / len(messages)
        
        # Generate markdown content
        content = f"""# Message Simulation: {config['topic'].title()}

## Metadata
- **Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **Topic**: {config['topic']}
- **Scenario**: {config['scenario_type']}
- **Complexity**: {config['complexity']}
- **Special Context**: {config['special_context']}

## Participants
{chr(10).join([f"- **{p['name']}** ({p['type']}, {p['role']})" for p in participants])}

## Statistics
- **Total Messages**: {len(messages)}
- **Human Messages**: {human_messages}
- **AI Messages**: {ai_messages}
- **Average Message Length**: {avg_length:.1f} characters

## Conversation

"""
        
        for msg in messages:
            emoji = "👤" if msg['sender_type'] == 'human' else "🤖"
            content += f"### {emoji} {msg['sender']} - {msg['timestamp_offset']}\n"
            content += f"*{msg['message_type']}*\n\n"
            content += f"{msg['content']}\n\n"
            content += "---\n\n"
        
        # Write to file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"💾 Simulation saved to: {filepath}")
        return str(filepath)
    
    def export_to_csv(self, messages: List[Dict], filename_base: str):
        """Export messages to CSV format for analysis."""
        csv_filepath = self.simulation_dir / f"{filename_base}.csv"
        
        with open(csv_filepath, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['message_id', 'sender', 'sender_type', 'timestamp_offset', 
                         'content', 'message_type', 'content_length']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            for msg in messages:
                row = msg.copy()
                row['content_length'] = len(msg['content'])
                writer.writerow(row)
        
        print(f"📊 CSV export saved to: {csv_filepath}")
    
    def run_simulation(self):
        """Run the complete simulation process."""
        print("🚀 Starting Message Simulation Generator")
        print("This tool will create realistic conversation data for testing message ontologies.")
        
        # Get configuration
        config = self.ask_configuration_questions()
        
        # Parse participants
        num_humans, num_ais = self.parse_participants(config['participants'])
        participants = self.generate_participants(num_humans, num_ais)
        
        print("\n📋 Simulation Configuration:")
        print(f"   Topic: {config['topic']}")
        print(f"   Scenario: {config['scenario_type']}")
        print(f"   Participants: {num_humans} humans, {num_ais} AI agents")
        print(f"   Complexity: {config['complexity']}")
        
        # Generate conversation
        messages = self.generate_conversation(config, participants)
        
        if not messages:
            print("❌ Failed to generate conversation. Exiting.")
            return
        
        # Save results
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        topic_clean = config['topic'].replace(" ", "_").replace("/", "_").lower()[:20]
        filename_base = f"{timestamp}_{topic_clean}"
        
        # Save markdown
        self.save_simulation(config, participants, messages)
        
        # Export CSV
        self.export_to_csv(messages, filename_base)
        
        print("\n✨ Simulation complete!")
        print("📁 Check the './message_simulations/' directory for outputs")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate realistic message exchange simulations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python messages_simulation.py
  python messages_simulation.py --api-key your_openai_key
        """
    )
    
    parser.add_argument(
        '--api-key',
        help='OpenAI API key (or set OPENAI_API_KEY environment variable)'
    )
    
    args = parser.parse_args()
    
    # Check for API key using project's secret system
    try:
        sys.path.append(str(Path(__file__).parent.parent.parent.parent.parent))
        from src import secret
        api_key = args.api_key or secret.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    except ImportError:
        api_key = args.api_key or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        print("❌ OpenAI API key required!")
        print("   Options:")
        print("   1. Use --api-key your_openai_key")
        print("   2. Set OPENAI_API_KEY environment variable")
        print("   3. Configure OPENAI_API_KEY in your project secrets")
        sys.exit(1)
    
    try:
        simulator = MessageSimulator(api_key)
        simulator.run_simulation()
    except KeyboardInterrupt:
        print("\n\n👋 Simulation cancelled by user.")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 
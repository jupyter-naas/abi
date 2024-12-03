import yaml
import os
from pathlib import Path
from typing import Dict, List, Any
import logging
import re
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OfferingsProcessor:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.bronze_dir = base_dir / 'data/l1_bronze/offerings'
        self.silver_dir = base_dir / 'data/l2_silver/offerings'
        self.gold_dir = base_dir / 'data/l3_gold/offerings'
        self.manual_data = None
        self.offerings_data = defaultdict(list)
        self.processed_data = {
            'classes': [],
            'entities': []
        }

    def clean_filename(self, name: str) -> str:
        """Clean filename using existing pattern"""
        clean = re.sub(r'[^\w\s-]', '', name)
        return clean.replace(' ', '_').lower()

    def load_manual_data(self):
        """Load the manual.yaml reference structure"""
        manual_path = self.gold_dir / 'market-offerings/manual.yaml'
        try:
            with open(manual_path, 'r', encoding='utf-8') as f:
                self.manual_data = yaml.safe_load(f)
            logger.info(f"Loaded manual structure from {manual_path}")
        except Exception as e:
            logger.error(f"Failed to load manual structure: {e}")
            raise

    def load_offerings_data(self):
        """Load all offerings data from bronze directory"""
        try:
            for file_path in self.bronze_dir.glob('**/*.yaml'):
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    if data and 'entities' in data:
                        group_name = file_path.stem
                        self.offerings_data[group_name].extend(data['entities'])
            logger.info(f"Loaded {len(self.offerings_data)} offering groups")
        except Exception as e:
            logger.error(f"Failed to load offerings data: {e}")
            raise

    def process_entity(self, entity: Dict, group: str) -> Dict:
        """Process and standardize an entity"""
        processed = {
            'id': entity.get('id'),
            'name': entity.get('name'),
            'definition': entity.get('definition', ''),
            'example': entity.get('example', ''),
            'style': {
                'group': entity.get('style', {}).get('group', group),
                'image': entity.get('style', {}).get('image', ''),
                'shape': entity.get('style', {}).get('shape', 'image'),
                'color': entity.get('style', {}).get('color', '#000000'),
                'x': entity.get('style', {}).get('x', 0),
                'y': entity.get('style', {}).get('y', 0)
            },
            'source': entity.get('source', ''),
            'relations': entity.get('relations', [])
        }
        return processed

    def merge_with_manual(self):
        """Merge offerings data with manual structure"""
        if self.manual_data:
            # Add manual entities first
            self.processed_data['entities'].extend(self.manual_data.get('entities', []))
            
        # Process and add offerings data
        for group, entities in self.offerings_data.items():
            for entity in entities:
                processed_entity = self.process_entity(entity, group)
                if not any(e['id'] == processed_entity['id'] for e in self.processed_data['entities']):
                    self.processed_data['entities'].append(processed_entity)

    def split_by_group(self):
        """Split processed data by group and save to separate files"""
        groups = defaultdict(lambda: {'classes': [], 'entities': []})
        
        for entity in self.processed_data['entities']:
            group = entity['style']['group']
            groups[group]['entities'].append(entity)

        # Save each group to a separate file
        for group_name, group_data in groups.items():
            filename = self.clean_filename(str(group_name)) + '.yaml'
            output_path = self.silver_dir / 'groups' / filename
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(group_data, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
            logger.info(f"Created group file: {filename}")

    def save_processed_data(self):
        """Save the complete processed data to gold directory"""
        output_path = self.gold_dir / 'offerings.yaml'
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.processed_data, f, default_flow_style=False, 
                         allow_unicode=True, sort_keys=False)
            logger.info(f"Saved processed data to {output_path}")
        except Exception as e:
            logger.error(f"Failed to save processed data: {e}")
            raise

    def process(self):
        """Run the complete processing pipeline"""
        self.load_manual_data()
        self.load_offerings_data()
        self.merge_with_manual()
        self.split_by_group()
        self.save_processed_data()

def main():
    base_dir = Path(__file__).parent.parent
    processor = OfferingsProcessor(base_dir)
    processor.process()

if __name__ == "__main__":
    main()
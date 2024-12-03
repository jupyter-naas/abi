import os

def generate_tree(startpath, exclude_dirs=None):
    if exclude_dirs is None:
        exclude_dirs = {'.git', '__pycache__', '.pytest_cache', '.venv', 'venv'}
    
    def get_tree_entries(path, prefix=''):
        entries = []
        try:
            items = os.listdir(path)
            # Separate directories and files
            dirs = sorted([d for d in items if os.path.isdir(os.path.join(path, d)) and d not in exclude_dirs])
            files = sorted([f for f in items if os.path.isfile(os.path.join(path, f)) and not f.startswith('.')])
            
            # Count items that will be processed
            total_items = len(dirs) + len(files)
            current_item = 0
            
            # Process directories first
            for d in dirs:
                current_item += 1
                is_last = current_item == total_items
                
                full_path = os.path.join(path, d)
                rel_path = os.path.relpath(full_path, startpath)
                
                if is_last:
                    entries.append(f'{prefix}└── {d}/')
                    new_prefix = prefix + '    '
                else:
                    entries.append(f'{prefix}├── {d}/')
                    new_prefix = prefix + '│   '
                
                # Recursively process subdirectories
                entries.extend(get_tree_entries(full_path, new_prefix))
            
            # Then process files
            for f in files:
                current_item += 1
                is_last = current_item == total_items
                
                if is_last:
                    entries.append(f'{prefix}└── {f}')
                else:
                    entries.append(f'{prefix}├── {f}')
                
        except PermissionError:
            pass
        
        return entries
    
    tree = get_tree_entries(startpath)
    return '\n'.join(tree)

def update_readme_structure():
    # Read existing README.md
    try:
        with open('README.md', 'r') as f:
            content = f.read()
    except FileNotFoundError:
        content = '# Project Name\n\n## Folder Structure\n'
    
    # Generate current structure
    tree = generate_tree('.')
    
    # Find and replace the folder structure section
    structure_marker = '## Folder Structure'
    if structure_marker in content:
        # Split content at the structure marker
        parts = content.split(structure_marker)
        
        # Find the next ## marker in the second part, if it exists
        second_part = parts[1]
        next_section = second_part.find('\n## ')
        
        if next_section != -1:
            # Keep the content after the next section marker
            remaining_content = second_part[next_section:]
            new_content = f'{parts[0]}{structure_marker}\n\n```\n{tree}\n```\n{remaining_content}'
        else:
            # No next section, just append the tree
            new_content = f'{parts[0]}{structure_marker}\n\n```\n{tree}\n```\n'
    else:
        # If no structure section exists, append it
        new_content = f'{content}\n{structure_marker}\n\n```\n{tree}\n```\n'
    
    # Write updated content back to README.md
    with open('README.md', 'w') as f:
        f.write(new_content)

if __name__ == '__main__':
    update_readme_structure()
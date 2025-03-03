import re
import csv
import os

def parse_linkedin_data(input_file, output_file):
    # Read the input file
    with open(input_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Split content by profile separators
    profiles_raw = content.split('Select LinkedIn Member')
    profiles = [p.strip() for p in profiles_raw if p.strip()]
    
    # Initialize CSV output
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Name', 'Connection_Degree', 'Title', 'Company', 'Location', 'Last_Activity', 'Activity_Notes', 'Date_Added']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Process each profile
        for profile in profiles:
            profile_data = {}
            lines = profile.split('\n')
            
            # Skip empty profiles
            if len(lines) < 5:
                continue
                
            # Extract name (first non-empty line)
            for line in lines:
                if line.strip():
                    profile_data['Name'] = line.strip()
                    break
            
            # Extract connection degree
            degree_text = next((line for line in lines if 'degree contact' in line), '')
            degree_match = re.search(r'(\d+)(?:st|nd|rd|th)', degree_text)
            profile_data['Connection_Degree'] = degree_match.group(1) if degree_match else ""
            
            # Find Saved Badge section which precedes title
            saved_badge_idx = -1
            for i, line in enumerate(lines):
                if 'Saved Badge' in line:
                    saved_badge_idx = i
                    break
            
            # Extract title and company (lines after "Saved Badge")
            if saved_badge_idx >= 0 and saved_badge_idx + 1 < len(lines):
                profile_data['Title'] = lines[saved_badge_idx + 1].strip()
                if saved_badge_idx + 2 < len(lines):
                    company_line = lines[saved_badge_idx + 2].strip()
                    profile_data['Company'] = company_line.split('(+')[0].strip() if '(+' in company_line else company_line
                else:
                    profile_data['Company'] = ""
            else:
                profile_data['Title'] = ""
                profile_data['Company'] = ""
            
            # Extract location (usually follows company)
            company_idx = -1
            for i, line in enumerate(lines):
                if profile_data['Company'] and profile_data['Company'] in line:
                    company_idx = i
                    break
            
            if company_idx >= 0 and company_idx + 1 < len(lines):
                profile_data['Location'] = lines[company_idx + 1].strip()
            else:
                profile_data['Location'] = ""
            
            # Extract activity status
            activity_status = ""
            for line in lines:
                if "was last active" in line:
                    activity_match = re.search(r'was last active (.*?)$', line)
                    if activity_match:
                        activity_status = f"Last active {activity_match.group(1)}"
                    break
                elif "is online" in line:
                    activity_status = "Online"
                    break
            profile_data['Last_Activity'] = activity_status
            
            # Extract activity notes
            add_note_idx = -1
            for i, line in enumerate(lines):
                if 'Add note' in line and i + 1 < len(lines):
                    add_note_idx = i
                    break
            
            if add_note_idx >= 0 and add_note_idx + 1 < len(lines):
                profile_data['Activity_Notes'] = lines[add_note_idx + 1].strip()
            else:
                profile_data['Activity_Notes'] = "No activity"
            
            # Extract date added
            date_match = re.search(r'(\d+/\d+/\d+)', profile)
            if date_match:
                profile_data['Date_Added'] = date_match.group(1)
            else:
                profile_data['Date_Added'] = ""
            
            # Clean up empty fields
            for key in profile_data:
                if profile_data[key] is None:
                    profile_data[key] = ""
            
            # Write the row
            writer.writerow(profile_data)
    
    print(f"Processed {len(profiles)} profiles to {output_file}")

# Run the parser
input_file = "storage/documents/People/linkedin_salesnav_data&ai_forvismazars.txt"
output_file = "forvis_mazars_contacts.csv"

if os.path.exists(input_file):
    parse_linkedin_data(input_file, output_file)
else:
    print(f"Input file not found: {input_file}") 
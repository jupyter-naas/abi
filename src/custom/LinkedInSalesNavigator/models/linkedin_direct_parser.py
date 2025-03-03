import csv
import re

# Sample of the data structure
sample_data = """
Select LinkedIn Member
Chantal Genermont

Chantal Genermont
1st degree contact
1st

1 List
Saved Badge
Partner
Forvis Mazars (+4)
France	

 Add note
3 weeks ago
 Message sent
2/24/2025	


Select LinkedIn Member
Dr. Benjamin Ballnus

Dr. Benjamin Ballnus
2nd degree contact
2nd

1 List
Saved Badge
Chief Data Officer (CDO), Forvis Mazars
Forvis Mazars in Germany
Leverkusen, North Rhine-Westphalia, Germany	

 Add note
No activity
2/24/2025	
"""

# Directly parse provided content
def parse_linkedin_content(content, output_file):
    # Split content by profile separators
    profiles_raw = content.split('Select LinkedIn Member')
    profiles = [p.strip() for p in profiles_raw if p.strip()]
    
    # Initialize CSV output
    with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['Name', 'Connection_Degree', 'Title', 'Company', 'Location', 'Last_Activity', 'Activity_Notes', 'Date_Added']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Process each profile
        parsed_count = 0
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
            parsed_count += 1
    
    print(f"Processed {parsed_count} profiles to {output_file}")

# Get the LinkedIn data from the file in the function call above
linkedin_content = """
```
Select LinkedIn Member
Chantal Genermont

Chantal Genermont
1st degree contact
1st

1 List
Saved Badge
Partner
Forvis Mazars (+4)
France	

 Add note
3 weeks ago
 Message sent
2/24/2025	


Select LinkedIn Member
Dr. Benjamin Ballnus

Dr. Benjamin Ballnus
2nd degree contact
2nd

1 List
Saved Badge
Chief Data Officer (CDO), Forvis Mazars
Forvis Mazars in Germany
Leverkusen, North Rhine-Westphalia, Germany	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Sean Hennessy

Sean Hennessy
2nd degree contact
2nd

1 List
Saved Badge
Head of IT Architecture
Forvis Mazars in the UK
London Area, United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Foyaz Uddin

Foyaz Uddin
2nd degree contact
2nd

1 List
Saved Badge
Director - Head of Data & Digital Advisory Services
Forvis Mazars in the UK
London, England, United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Asam Malik

Asam Malik
2nd degree contact
2nd

1 List
Saved Badge
Partner | UK Executive Board Member | Head of Digital & Risk Consulting
Forvis Mazars in the UK
London, England, United Kingdom	

 Add note
2 months ago
 Invitation sent
2/24/2025	


Select LinkedIn Member
Natarad Sornsaksit

Natarad Sornsaksit
3rd degree contact
3rd

1 List
Saved Badge
AI Consultant
Forvis Mazars In Ireland
Dublin, County Dublin, Ireland	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Claire Cizaire, PhD

Claire Cizaire, PhD
2nd degree contact
2nd

1 List
Saved Badge
Group Chief Technology and Innovation Officer
Forvis Mazars Group
France	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Arash Jourshari

Arash Jourshari
2nd degree contact
2nd

1 List
Saved Badge
Senior Manager Digital Tax - Data & AI
Forvis Mazars in Germany
Berlin Metropolitan Area	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Kevin Le Denic
Kevin Le Denic is online
Kevin Le Denic
1st degree contact
1st

1 List
Saved Badge
Partner Data Advisory Forvis Mazars
Forvis Mazars Group
France	

 Add note
11 hours ago
 Message sent
2/24/2025	


Select LinkedIn Member
Lorne H.

Lorne H.
2nd degree contact
2nd

1 List
Saved Badge
Information Security Analyst
Forvis Mazars US
Springfield, Missouri, United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Kevin LABBÉ

Kevin LABBÉ
2nd degree contact
2nd

1 List
Saved Badge
Sr. Group Engineering Manager / TPM | Product Engineering & Innovation
Forvis Mazars Group
Paris, Île-de-France, France	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Gary C

Gary C
2nd degree contact
2nd

1 List
Saved Badge
Global Head of Identity & Access Management
Forvis Mazars Group
Silverstone, England, United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Stanislas Fontanges

Stanislas Fontanges
2nd degree contact
2nd

1 List
Saved Badge
Consultant - Performance & Transformation de la fonction Finance
Forvis Mazars Group (+1)
France	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Christian Segurado, B.Eng., MBA, MCP, MCT, Microsoft MVP
Christian Segurado, B.Eng., MBA, MCP, MCT, Microsoft MVP was last active 4 hours ago
Christian Segurado, B.Eng., MBA, MCP, MCT, Microsoft MVP
2nd degree contact
2nd

1 List
Saved Badge
Senior Manager
Forvis Mazars US
New York, New York, United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Shree Parthasarathy

Shree Parthasarathy
2nd degree contact
2nd

1 List
Saved Badge
Partner Consulting & Leader (Digital, Trust & Transformation)
Forvis Mazars in India
Greater Delhi Area	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Thierno Mansour DIALLO

Thierno Mansour DIALLO
1st degree contact
1st

2 Lists
Saved Badge
Senior Manager | Data & AI Leader
Forvis Mazars en France (+1)
Paris, Île-de-France, France	

 Add note
1 week ago
 Invitation accepted
2/24/2025	


Select LinkedIn Member
Prashant Pandit

Prashant Pandit
3rd degree contact
3rd

1 List
Saved Badge
Data Analyst Manager
Forvis Mazars in the UK
Redhill, England, United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Phillip Richards, CSM

Phillip Richards, CSM
2nd degree contact
2nd

1 List
Saved Badge
Senior Innovation Product Owner
Forvis Mazars US
Charlotte, North Carolina, United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Syed Adees Gillani

Syed Adees Gillani
2nd degree contact
2nd

1 List
Saved Badge
Data Audit Analyst
Forvis Mazars in the UK
London, England, United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Irene X.

Irene X.
3rd degree contact
3rd

1 List
Saved Badge
Data Analyst
Forvis Mazars in the UK
United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Alexandre Biguenet

Alexandre Biguenet
2nd degree contact
2nd

1 List
Saved Badge
CSR Manager
Forvis Mazars en France
Greater Paris Metropolitan Region	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Nour Ben Rejeb

Nour Ben Rejeb
2nd degree contact
2nd

1 List
Saved Badge
Data & AI consultant
Forvis Mazars Group
Paris, Île-de-France, France	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Henri-Louis Boisvert

Henri-Louis Boisvert
3rd degree contact
3rd

1 List
Saved Badge
Network Senior Data Analyst
Forvis Mazars
London, England, United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Luke Sheehy

Luke Sheehy
3rd degree contact
3rd

1 List
Saved Badge
Data Protection and Privacy Associate
Forvis Mazars In Ireland
Ireland	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Burmachach Nuradilova

Burmachach Nuradilova
2nd degree contact
2nd

1 List
Saved Badge
Junior Data Scientist
Forvis Mazars Group
Bishkek City, Kyrgyzstan	

 Add note
No activity
2/24/2025

Laurent INARD was last active 14 hours ago
Laurent INARD
1st degree contact
1st

1 List
Saved Badge
Partner - Supervisory Board Member – Chief R&D Officer | Valuation & Models, Data Advisory
Forvis Mazars en France (+1)
Greater Paris Metropolitan Region	

 Add note
6 months ago
 Invitation accepted
2/24/2025	


Select LinkedIn Member
Michelle Kyriakakis, CPA

Michelle Kyriakakis, CPA
3rd degree contact
3rd

1 List
Saved Badge
Tax Manager
Forvis Mazars
Greenville-Spartanburg-Anderson, South Carolina Area	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Vijay Navaluri

Vijay Navaluri
2nd degree contact
2nd

1 List
Saved Badge
Co-Founder & Chief Customer Officer
Supervity (+2)
United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Paulo Leeanzo Hipolito

Paulo Leeanzo Hipolito
3rd degree contact
3rd

1 List
Saved Badge
Senior Auditor
Forvis Mazars
Malvar, Calabarzon, Philippines	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Noman Zafar

Noman Zafar
2nd degree contact
2nd

1 List
Saved Badge
Director, Actuarial & Risk Services at Mazars
Forvis Mazars In Ireland
Dublin, County Dublin, Ireland	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Seerat Zargar

Seerat Zargar
2nd degree contact
2nd

1 List
Saved Badge
Assistant Manager
Forvis Mazars Group
London, England, United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Rony James

Rony James
3rd degree contact
3rd

1 List
Saved Badge
Audit Associate
Forvis Mazars In Ireland
Galway, County Galway, Ireland	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Emily Alps

Emily Alps
2nd degree contact
2nd

1 List
Saved Badge
Consultant - Transfer Pricing
Forvis Mazars US (+1)
Charlotte, North Carolina, United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Kayla C.

Kayla C.
3rd degree contact
3rd

1 List
Saved Badge
Senior Consultant - Federal Tax Specialty Services
Forvis Mazars US
New York, New York, United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Vaishali Iyer

Vaishali Iyer
3rd degree contact
3rd

1 List
Saved Badge
Compliance Senior
Forvis Mazars In Ireland
Dublin, County Dublin, Ireland	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Timofei Kornev

Timofei Kornev
2nd degree contact
2nd

1 List
Saved Badge
Consultant - Data & Analytics
Forvis Mazars in Germany
Berlin Metropolitan Area	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Sarah Gavin

Sarah Gavin
3rd degree contact
3rd

1 List
Saved Badge
Senior Auditor
Forvis Mazars In Ireland
County Galway, Ireland	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Grant Ugarte, CPA

Grant Ugarte, CPA
3rd degree contact
3rd

1 List
Saved Badge
Tax Associate
Forvis Mazars US
Chicago, Illinois, United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Emeric Letocart

Emeric Letocart
3rd degree contact
3rd

1 List
Saved Badge
Auditeur financier et informatique
Forvis Mazars en France
Greater Paris Metropolitan Region	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Suraj Krishnamurthy

Suraj Krishnamurthy
3rd degree contact
3rd

1 List
Saved Badge
Working Student
Forvis Mazars in Germany
Frankfurt, Hesse, Germany	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Gaurav Kalal

Gaurav Kalal
2nd degree contact
2nd

1 List
Saved Badge
Automation Analyst
Forvis Mazars in the UK
Pune/Pimpri-Chinchwad Area	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Diya Sankla

Diya Sankla
3rd degree contact
3rd

1 List
Saved Badge
Technical Analyst
Enactus UK & Ireland (+2)
Maidenhead, England, United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Andrea V.

Andrea V.
3rd degree contact
3rd

1 List
Saved Badge
Accounting Consultant
Forvis Mazars Group
Milan, Lombardy, Italy	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Sunzida Faiz
Sunzida Faiz was last active 3 days ago
Sunzida Faiz
3rd degree contact
3rd

1 List
Saved Badge
Audit Associate
Forvis Mazars US
United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Daniel Roberto Quines

Daniel Roberto Quines
2nd degree contact
2nd

1 List
Saved Badge
Jr Global Coordinator | International PMO
Forvis Mazars Group
Barcelona, Catalonia, Spain	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Shatakshi Gupta

Shatakshi Gupta
3rd degree contact
3rd

1 List
Saved Badge
Associate Consultant
Forvis Mazars in India
Gurugram, Haryana, India	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Sona Grigoryan

Sona Grigoryan
3rd degree contact
3rd

1 List
Saved Badge
Werkstudent
Forvis Mazars in Germany
Cologne Bonn Region	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Bhaveshni Mundhoo

Bhaveshni Mundhoo
3rd degree contact
3rd

1 List
Saved Badge
Payroll Associate
Forvis Mazars In Ireland
Dublin, County Dublin, Ireland	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Graham Burnett

Graham Burnett
3rd degree contact
3rd

1 List
Saved Badge
Group Leadership, Eduation & Culture - Forvis Mazars Group
Forvis Mazars Group
Sunderland, England, United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Frederick Junior Komla Z.

Frederick Junior Komla Z.
3rd degree contact
3rd

1 List
Saved Badge
Audit Senior
Forvis Mazars Group
Accra, Greater Accra Region, Ghana	

 Add note
No activity
2/24/2025	


Name	Account	Geography	Notes Tooltip
Outreach activity	Date added	Actions

Select LinkedIn Member
Marwa Murisi, CF APMP

Marwa Murisi, CF APMP
2nd degree contact
2nd

1 List
Saved Badge
Global Compliance & Reporting Board Project Management, Manager
Forvis Mazars Group
Bucharest, Romania	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Anastasia K.

Anastasia K.
2nd degree contact
2nd

1 List
Saved Badge
Senior Product Line Manager
Forvis Mazars US
Raleigh-Durham-Chapel Hill Area	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Ceyda Çakmak

Ceyda Çakmak
3rd degree contact
3rd

1 List
Saved Badge
Assistant Manager
Forvis Mazars In Ireland
Dublin, County Dublin, Ireland	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Tonya R.

Tonya R.
3rd degree contact
3rd

1 List
Saved Badge
Change Management consulting
Forvis Mazars in the UK
London, England, United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
David J.

David J.
3rd degree contact
3rd

1 List
Saved Badge
Manager
Forvis Mazars in the UK
United Kingdom	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Darien Sutton, RAI

Darien Sutton, RAI
2nd degree contact
2nd

1 List
Saved Badge
Director, Enterprise Risk & Quantitative Consulting
Forvis Mazars US (+1)
Winston-Salem, North Carolina, United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Bhavik Chagan, FMVA®

Bhavik Chagan, FMVA®
3rd degree contact
3rd

1 List
Saved Badge
Project Finance Analyst
Forvis Mazars Group
City of Johannesburg, Gauteng, South Africa	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Simone Aprea

Simone Aprea
3rd degree contact
3rd

1 List
Saved Badge
Consultant • IT Risk & Advisory
Forvis Mazars Group
Livorno, Tuscany, Italy	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Kaeli Lange, RAI

Kaeli Lange, RAI
3rd degree contact
3rd

1 List
Saved Badge
Senior Consultant, Quantitative Solutions
Forvis Mazars US
United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Anuj Srivastava

Anuj Srivastava
3rd degree contact
3rd

1 List
Saved Badge
Senior Consultant
Forvis Mazars in India
Delhi, India	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Farah Keeton

Farah Keeton
3rd degree contact
3rd

1 List
Saved Badge
Software Systems Analyst | WeCheck
Forvis Mazars
United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Aibek Mambetkaziev

Aibek Mambetkaziev
2nd degree contact
2nd

1 List
Saved Badge
Digital Consultant
Forvis Mazars Group
Bishkek City, Kyrgyzstan	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Ethan Michel

Ethan Michel
3rd degree contact
3rd

1 List
Saved Badge
Systems Integration Consultant
Forvis Mazars US
New York, New York, United States	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Shina Sehgal, CAMS, CRCMP

Shina Sehgal, CAMS, CRCMP
2nd degree contact
2nd

1 List
Saved Badge
Assistant Manager
Forvis Mazars in India
Delhi, India	

 Add note
No activity
2/24/2025	


Select LinkedIn Member
Weronika Maria Jasinska

Weronika Maria Jasinska
3rd degree contact
3rd

1 List
Saved Badge
Risk Consultant and Internal Audit Associate
Forvis Mazars In Ireland
Dublin, County Dublin, Ireland	

 Add note
No activity
2/24/2025	
```
"""

# Remove Markdown backticks and clean up the content
linkedin_content = linkedin_content.replace("```", "")

# Parse the content directly into CSV
parse_linkedin_content(linkedin_content, "forvis_mazars_contacts.csv") 
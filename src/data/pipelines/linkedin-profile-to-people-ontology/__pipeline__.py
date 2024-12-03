from typing import List
from pathlib import Path
from .get_linkedin_profile import get_profile_data
from .send_to_ontology import send_profile_to_ontology

def process_linkedin_profile(linkedin_url: str, output_dir: str) -> None:
    """
    Pipeline to process LinkedIn profile data and convert it to ontology format
    
    Args:
        linkedin_url: URL of the LinkedIn profile to process
        output_dir: Directory to save the output TTL file
    """
    try:
        # Step 1: Get LinkedIn profile data
        profile_data = get_profile_data(linkedin_url)
        
        # Create output directory if it doesn't exist
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate output filename based on profile name or ID
        profile_name = profile_data.get('personal_info', {}).get('full_name', 'unknown')
        profile_name = profile_name.lower().replace(' ', '_')
        output_file = output_path / f"{profile_name}_profile.ttl"
        
        # Step 2: Convert and save to ontology
        send_profile_to_ontology(profile_data, str(output_file))
        
        return {
            "status": "success",
            "profile_name": profile_name,
            "output_file": str(output_file)
        }
        
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "linkedin_url": linkedin_url
        }

def batch_process_profiles(linkedin_urls: List[str], output_dir: str) -> List[dict]:
    """
    Process multiple LinkedIn profiles in batch
    
    Args:
        linkedin_urls: List of LinkedIn profile URLs to process
        output_dir: Directory to save the output TTL files
        
    Returns:
        List of processing results for each profile
    """
    results = []
    
    for url in linkedin_urls:
        result = process_linkedin_profile(url, output_dir)
        results.append(result)
    
    return results
#!/usr/bin/env python3
"""
Script to create a comprehensive Marketplace banner with both domain experts and application logos
Generates a full-width banner showcasing the complete ABI marketplace ecosystem
"""

from PIL import Image, ImageDraw
import requests
import os
import argparse
from pathlib import Path

# Domain Expert logos (existing)
DOMAIN_EXPERTS = [
    "software-engineer.png",
    "data-engineer.png", 
    "devops-engineer.png",
    "content-creator.png",
    "content-strategist.png",
    "content-analyst.png",
    "project-manager.png",
    "account-executive.png",
    "sales-development-representative.png",
    "business-development-representative.png",
    "campaign-manager.png",
    "community-manager.png",
    "customer-success-manager.png",
    "accountant.png",
    "financial-controller.png",
    "treasurer.png",
    "human-resources-manager.png",
    "osint-researcher.png",
    "private-investigator.png",
    "inside-sales-representative.png"
]

# Application Integration logos (to be added)
APPLICATION_INTEGRATIONS = [
    "github.png",
    "linkedin.png", 
    "google-search.png",
    "postgresql.png",
    "algolia.png",
    "arxiv.png",
    "naas.png",
    "git.png",
    "powerpoint.png",
    "exchangeratesapi.png"
]

# Logo sources for application integrations
APPLICATION_LOGO_SOURCES = {
    "github.png": "https://github.githubassets.com/images/modules/logos_page/GitHub-Mark.png",
    "linkedin.png": "https://content.linkedin.com/content/dam/me/business/en-us/amp/brand-site/v2/bg/LI-Bug.svg.original.svg",
    "google-search.png": "https://www.google.com/images/branding/googlelogo/2x/googlelogo_color_272x92dp.png",
    "postgresql.png": "https://cdn.iconscout.com/icon/free/png-256/postgresql-11-1175122.png",
    "algolia.png": "https://www.algolia.com/static_assets/images/press/downloads/algolia-mark-blue.svg",
    "arxiv.png": "https://arxiv.org/static/browse/0.3.4/images/arxiv-logo-fb.png",
    "naas.png": "https://avatars.githubusercontent.com/u/54785633?s=200&v=4",
    "git.png": "https://git-scm.com/images/logos/downloads/Git-Icon-1788C.png",
    "powerpoint.png": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0d/Microsoft_Office_PowerPoint_%282019%E2%80%93present%29.svg/1200px-Microsoft_Office_PowerPoint_%282019%E2%80%93present%29.svg.png",
    "exchangeratesapi.png": "https://exchangeratesapi.io/img/logo.png"
}

def download_logo(url, filepath):
    """Download a logo from URL to filepath"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, timeout=10, headers=headers)
        response.raise_for_status()
        
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ Downloaded: {filepath.name}")
        return True
    except Exception as e:
        print(f"⚠️  Failed to download {url}: {e}")
        return False

def create_rounded_image(img_path, size=(80, 80), radius_percent=0.2):
    """
    Create a rounded version of an image with consistent size
    
    Args:
        img_path: Path to input image
        size: Target size (width, height)
        radius_percent: Corner radius as percentage of size
    """
    try:
        # Open and resize image
        img = Image.open(img_path).convert("RGBA")
        img = img.resize(size, Image.Resampling.LANCZOS)
        
        width, height = size
        radius = int(min(width, height) * radius_percent)
        
        # Create mask for rounded corners
        mask = Image.new('L', size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), size], radius=radius, fill=255)
        
        # Apply mask
        output = Image.new('RGBA', size, (0, 0, 0, 0))
        output.paste(img, (0, 0))
        output.putalpha(mask)
        
        return output
    except Exception as e:
        print(f"⚠️  Error processing {img_path}: {e}")
        return None

def create_marketplace_banner(
    domain_experts_dir="assets/domain-experts",
    applications_dir="assets/applications",
    output_path="assets/marketplace-banner.png", 
    logo_size=(80, 80),  # Standard ABI banner size
    spacing=20,          # Standard ABI banner spacing
    max_per_row=15,      # Full width layout
    background_color=(255, 255, 255, 0)  # Transparent
):
    """
    Create a comprehensive marketplace banner with domain experts and applications
    
    Args:
        domain_experts_dir: Directory containing domain expert logos
        applications_dir: Directory containing application logos
        output_path: Where to save the banner
        logo_size: Size of each logo (width, height)
        spacing: Pixels between logos
        max_per_row: Maximum logos per row
        background_color: RGBA background color
    """
    domain_path = Path(domain_experts_dir)
    apps_path = Path(applications_dir)
    
    # Create applications directory if it doesn't exist
    apps_path.mkdir(exist_ok=True)
    
    # Download missing application logos
    print("🔽 Downloading application integration logos...")
    for logo_name, url in APPLICATION_LOGO_SOURCES.items():
        logo_path = apps_path / logo_name
        if not logo_path.exists():
            download_logo(url, logo_path)
    
    # Collect all available logos
    all_logos = []
    
    # Add domain expert logos
    print("📋 Collecting domain expert logos...")
    for expert_file in DOMAIN_EXPERTS:
        expert_path = domain_path / expert_file
        if expert_path.exists():
            all_logos.append(expert_path)
        else:
            print(f"⚠️  Domain expert logo not found: {expert_path}")
    
    # Add application logos
    print("📋 Collecting application integration logos...")
    for app_file in APPLICATION_INTEGRATIONS:
        app_path = apps_path / app_file
        if app_path.exists():
            all_logos.append(app_path)
        else:
            print(f"⚠️  Application logo not found: {app_path}")
    
    if not all_logos:
        print("❌ No marketplace logos found!")
        return False
    
    print(f"🎯 Found {len(all_logos)} total marketplace logos")
    print(f"   - Domain Experts: {len([l for l in all_logos if 'domain-experts' in str(l)])}")
    print(f"   - Applications: {len([l for l in all_logos if 'applications' in str(l)])}")
    
    # Create rounded versions
    rounded_logos = []
    for logo_path in all_logos:
        rounded = create_rounded_image(logo_path, logo_size)
        if rounded:
            rounded_logos.append(rounded)
            print(f"✅ Processed: {logo_path.name}")
    
    if not rounded_logos:
        print("❌ No logos could be processed!")
        return False
    
    # Calculate banner dimensions
    logos_count = len(rounded_logos)
    rows = (logos_count + max_per_row - 1) // max_per_row  # Ceiling division
    cols = min(logos_count, max_per_row)
    
    banner_width = cols * logo_size[0] + (cols - 1) * spacing
    banner_height = rows * logo_size[1] + (rows - 1) * spacing
    
    print(f"📐 Banner: {banner_width}x{banner_height}px ({rows} rows, {cols} cols max)")
    
    # Create banner
    banner = Image.new('RGBA', (banner_width, banner_height), background_color)
    
    # Place logos
    for i, logo in enumerate(rounded_logos):
        row = i // max_per_row
        col = i % max_per_row
        
        x = col * (logo_size[0] + spacing)
        y = row * (logo_size[1] + spacing)
        
        banner.paste(logo, (x, y), logo)
    
    # Save banner
    banner.save(output_path, "PNG")
    print(f"🎉 Created comprehensive marketplace banner: {output_path}")
    print(f"   Size: {banner_width}x{banner_height}px")
    print(f"   Total logos: {logos_count} ({rows} rows)")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Create comprehensive marketplace banner for ABI")
    parser.add_argument("--domain-experts-dir", default="assets/domain-experts", help="Domain experts directory")
    parser.add_argument("--applications-dir", default="assets/applications", help="Applications directory")
    parser.add_argument("--output", default="assets/marketplace-banner.png", help="Output file")
    parser.add_argument("--size", type=int, default=80, help="Logo size (square)")
    parser.add_argument("--spacing", type=int, default=20, help="Spacing between logos")
    parser.add_argument("--per-row", type=int, default=15, help="Max logos per row")
    parser.add_argument("--transparent", action="store_true", help="Transparent background")
    
    args = parser.parse_args()
    
    logo_size = (args.size, args.size)
    bg_color = (255, 255, 255, 0) if args.transparent else (255, 255, 255, 255)
    
    success = create_marketplace_banner(
        domain_experts_dir=args.domain_experts_dir,
        applications_dir=args.applications_dir,
        output_path=args.output,
        logo_size=logo_size,
        spacing=args.spacing,
        max_per_row=args.per_row,
        background_color=bg_color
    )
    
    if success:
        print(f"\n🚀 Usage in README:")
        print(f'<img src="{args.output}" alt="Complete Marketplace Ecosystem" width="100%">')
    else:
        print("❌ Failed to create banner")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Script to create an Automation & Orchestration banner with technology logos
Uses existing logos from assets/automation-orchestration directory
"""

from PIL import Image, ImageDraw
import requests
import os
import argparse
from pathlib import Path

# Automation & Orchestration logos (in preferred order)
AUTOMATION_LOGOS = [
    "python.png",
    "fastapi.png",
    "streamlit.png",
    "dagster.jpg", 
    "docker.png",
    "github.png",
    "ollama.png",
    "naas.png",
    "browser-use.png",
    "chromium.png"
]

# Logo sources for missing technologies
MISSING_LOGO_SOURCES = {
    "fastapi.png": "https://fastapi.tiangolo.com/img/logo-margin/logo-teal.png",
    "streamlit.png": "https://streamlit.io/images/brand/streamlit-logo-primary-colormark-darktext.png",
    "ollama.png": "https://ollama.com/public/ollama.png",
    "naas.png": "https://avatars.githubusercontent.com/u/54785633?s=200&v=4"
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

def create_automation_orchestration_banner(
    assets_dir="assets/automation-orchestration",
    output_path="assets/automation-orchestration-banner.png", 
    logo_size=(80, 80),  # Standard ABI banner size
    spacing=20,          # Standard ABI banner spacing
    max_per_row=5,       # 2 rows of 5 for 10 logos
    background_color=(255, 255, 255, 0)  # Transparent
):
    """
    Create a banner with automation & orchestration technology logos
    
    Args:
        assets_dir: Directory containing logo files
        output_path: Where to save the banner
        logo_size: Size of each logo (width, height)
        spacing: Pixels between logos
        max_per_row: Maximum logos per row
        background_color: RGBA background color
    """
    assets_path = Path(assets_dir)
    
    # Download missing logos
    print("🔽 Downloading missing automation & orchestration logos...")
    for logo_name, url in MISSING_LOGO_SOURCES.items():
        logo_path = assets_path / logo_name
        if not logo_path.exists():
            download_logo(url, logo_path)
    
    # Find available automation logos
    available_logos = []
    for logo_file in AUTOMATION_LOGOS:
        logo_path = assets_path / logo_file
        if logo_path.exists():
            available_logos.append(logo_path)
        else:
            print(f"⚠️  Logo not found: {logo_path}")
    
    if not available_logos:
        print("❌ No automation & orchestration logos found!")
        return False
    
    print(f"🎯 Found {len(available_logos)} automation & orchestration logos")
    
    # Create rounded versions
    rounded_logos = []
    for logo_path in available_logos:
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
    print(f"🎉 Created automation & orchestration banner: {output_path}")
    print(f"   Size: {banner_width}x{banner_height}px")
    print(f"   Logos: {logos_count} ({rows} rows)")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Create automation & orchestration banner for ABI")
    parser.add_argument("--assets-dir", default="assets/automation-orchestration", help="Assets directory")
    parser.add_argument("--output", default="assets/automation-orchestration-banner.png", help="Output file")
    parser.add_argument("--size", type=int, default=80, help="Logo size (square)")
    parser.add_argument("--spacing", type=int, default=20, help="Spacing between logos")
    parser.add_argument("--per-row", type=int, default=3, help="Max logos per row")
    parser.add_argument("--transparent", action="store_true", help="Transparent background")
    
    args = parser.parse_args()
    
    logo_size = (args.size, args.size)
    bg_color = (255, 255, 255, 0) if args.transparent else (255, 255, 255, 255)
    
    success = create_automation_orchestration_banner(
        assets_dir=args.assets_dir,
        output_path=args.output,
        logo_size=logo_size,
        spacing=args.spacing,
        max_per_row=args.per_row,
        background_color=bg_color
    )
    
    if success:
        print(f"\n🚀 Usage in README:")
        print(f'<img src="{args.output}" alt="Automation & Orchestration Technologies" width="300">')
    else:
        print("❌ Failed to create banner")

if __name__ == "__main__":
    main()

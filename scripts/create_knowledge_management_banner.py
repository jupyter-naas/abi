#!/usr/bin/env python3
"""
Script to create a Knowledge Management banner with semantic web standard logos
Downloads and processes W3C, OWL, JSON-LD, and ISO 21838 logos
"""

from PIL import Image, ImageDraw
import requests
import os
import argparse
from pathlib import Path

# Knowledge Management logos and their sources
KNOWLEDGE_LOGOS = {
    "w3c.png": "https://www.w3.org/Icons/w3c_home.png",
    "semantic-web.png": "https://www.w3.org/Icons/SW/sw-horz-w3c.png", 
    "json-ld.png": "https://json-ld.org/images/json-ld-logo-64.png",
    "rdf.png": "https://www.w3.org/RDF/icons/rdf_w3c_icon.128.gif",
    "iso.png": "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/ISO_Logo_%28Red_square%29.svg/1200px-ISO_Logo_%28Red_square%29.svg.png"
}

def download_logo(url, filepath):
    """Download a logo from URL to filepath"""
    try:
        response = requests.get(url, timeout=10)
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

def create_knowledge_management_banner(
    assets_dir="assets/knowledge-management",
    output_path="assets/knowledge-management-banner.png", 
    logo_size=(80, 80),  # Standard ABI banner size
    spacing=20,          # Standard ABI banner spacing
    max_per_row=4,
    background_color=(255, 255, 255, 0),  # Transparent
    download_logos=True
):
    """
    Create a banner with knowledge management standard logos
    
    Args:
        assets_dir: Directory containing knowledge management logo files
        output_path: Where to save the banner
        logo_size: Size of each logo (width, height)
        spacing: Pixels between logos
        max_per_row: Maximum logos per row
        background_color: RGBA background color
        download_logos: Whether to download logos if missing
    """
    assets_path = Path(assets_dir)
    assets_path.mkdir(exist_ok=True)
    
    # Download logos if requested
    if download_logos:
        print("🌐 Downloading knowledge management logos...")
        for filename, url in KNOWLEDGE_LOGOS.items():
            logo_path = assets_path / filename
            if not logo_path.exists():
                download_logo(url, logo_path)
            else:
                print(f"✅ Already exists: {filename}")
    
    # Find available logos
    available_logos = []
    for filename in KNOWLEDGE_LOGOS.keys():
        logo_path = assets_path / filename
        if logo_path.exists():
            available_logos.append(logo_path)
        else:
            print(f"⚠️  Logo not found: {logo_path}")
    
    if not available_logos:
        print("❌ No knowledge management logos found!")
        return False
    
    print(f"🎯 Found {len(available_logos)} knowledge management logos")
    
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
    print(f"🎉 Created knowledge management banner: {output_path}")
    print(f"   Size: {banner_width}x{banner_height}px")
    print(f"   Standards: {logos_count} ({rows} rows)")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Create knowledge management banner for ABI README")
    parser.add_argument("--assets-dir", default="assets/knowledge-management", help="Knowledge management assets directory")
    parser.add_argument("--output", default="assets/knowledge-management-banner.png", help="Output file")
    parser.add_argument("--size", type=int, default=80, help="Logo size (square) - Standard ABI banner size")
    parser.add_argument("--spacing", type=int, default=20, help="Spacing between logos - Standard ABI banner spacing")
    parser.add_argument("--per-row", type=int, default=4, help="Max logos per row")
    parser.add_argument("--transparent", action="store_true", help="Transparent background")
    parser.add_argument("--no-download", action="store_true", help="Skip downloading logos")
    
    args = parser.parse_args()
    
    logo_size = (args.size, args.size)
    bg_color = (255, 255, 255, 0) if args.transparent else (255, 255, 255, 255)
    
    success = create_knowledge_management_banner(
        assets_dir=args.assets_dir,
        output_path=args.output,
        logo_size=logo_size,
        spacing=args.spacing,
        max_per_row=args.per_row,
        background_color=bg_color,
        download_logos=not args.no_download
    )
    
    if success:
        print(f"\n🚀 Usage in README:")
        print(f'<img src="{args.output}" alt="Knowledge Management Standards" width="350">')
        print(f"\n📚 Standards included:")
        print("- W3C: World Wide Web Consortium")
        print("- OWL: Web Ontology Language") 
        print("- JSON-LD: Linked Data format")
        print("- RDF: Resource Description Framework")
        print("- ISO: International Organization for Standardization")
    else:
        print("❌ Failed to create banner")

if __name__ == "__main__":
    main()

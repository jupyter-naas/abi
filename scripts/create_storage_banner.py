#!/usr/bin/env python3
"""
Script to create a Storage banner with core storage technology logos
Downloads and processes PostgreSQL, Qdrant, and AWS S3 logos
"""

from PIL import Image, ImageDraw
import requests
import os
import argparse
from pathlib import Path

# Storage technology logos and their sources
STORAGE_LOGOS = {
    "postgresql.png": "https://cdn.iconscout.com/icon/free/png-256/postgresql-11-1175122.png",
    "qdrant.png": "https://qdrant.tech/images/logo_with_text.svg", 
    "aws-s3.png": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/Amazon-S3-Logo.svg/1200px-Amazon-S3-Logo.svg.png",
    "oxigraph.png": "https://avatars.githubusercontent.com/u/64649343?s=200&v=4",
    "aws-neptune.png": "https://dbdb.io/media/logos/amazon-neptune.png"
}

# Alternative sources if primary fails
STORAGE_LOGOS_ALT = {
    "postgresql.png": [
        "https://cdn.iconscout.com/icon/free/png-256/postgresql-11-1175122.png",
        "https://www.postgresql.org/media/img/about/press/elephant.png"
    ],
    "qdrant.png": [
        "https://avatars.githubusercontent.com/u/73504361?s=200&v=4",
        "https://raw.githubusercontent.com/qdrant/qdrant/master/docs/logo.svg"
    ],
    "aws-s3.png": [
        "https://cdn.worldvectorlogo.com/logos/aws-s3.svg",
        "https://d0.awsstatic.com/logos/powered-by-aws.png"
    ],
    "oxigraph.png": [
        "https://github.com/oxigraph/oxigraph/raw/main/logo.svg",
        "https://raw.githubusercontent.com/oxigraph/oxigraph/main/logo.svg"
    ],
    "aws-neptune.png": [
        "https://d1.awsstatic.com/product-marketing/Neptune/neptune-icon.png",
        "https://aws.amazon.com/neptune/faqs/neptune-icon.png"
    ]
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

def try_download_with_alternatives(logo_name, storage_dir):
    """Try downloading a logo with primary and alternative sources"""
    filepath = storage_dir / logo_name
    
    # Try primary source
    if logo_name in STORAGE_LOGOS:
        if download_logo(STORAGE_LOGOS[logo_name], filepath):
            return True
    
    # Try alternatives
    if logo_name in STORAGE_LOGOS_ALT:
        for alt_url in STORAGE_LOGOS_ALT[logo_name]:
            if download_logo(alt_url, filepath):
                return True
    
    print(f"❌ Could not download {logo_name} from any source")
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

def create_storage_banner(
    assets_dir="assets",
    output_path="assets/storage-banner.png", 
    logo_size=(80, 80),  # Standard ABI banner size
    spacing=20,          # Standard ABI banner spacing
    background_color=(255, 255, 255, 0)  # Transparent
):
    """
    Create a banner with storage technology logos
    
    Args:
        assets_dir: Directory containing logo files
        output_path: Where to save the banner
        logo_size: Size of each logo (width, height)
        spacing: Pixels between logos
        background_color: RGBA background color
    """
    assets_path = Path(assets_dir)
    storage_dir = assets_path / "storage"
    
    # Create storage subdirectory if it doesn't exist
    storage_dir.mkdir(exist_ok=True)
    
    # Download missing logos
    print("🔽 Downloading storage technology logos...")
    for logo_name in STORAGE_LOGOS.keys():
        logo_path = storage_dir / logo_name
        if not logo_path.exists():
            try_download_with_alternatives(logo_name, storage_dir)
    
    # Find available storage logos
    available_logos = []
    for logo_name in STORAGE_LOGOS.keys():
        logo_path = storage_dir / logo_name
        if logo_path.exists():
            available_logos.append(logo_path)
        else:
            print(f"⚠️  Logo not found: {logo_path}")
    
    if not available_logos:
        print("❌ No storage logos found!")
        return False
    
    print(f"🎯 Found {len(available_logos)} storage logos")
    
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
    
    # Calculate banner dimensions (single row)
    logos_count = len(rounded_logos)
    banner_width = logos_count * logo_size[0] + (logos_count - 1) * spacing
    banner_height = logo_size[1]
    
    print(f"📐 Banner: {banner_width}x{banner_height}px ({logos_count} logos)")
    
    # Create banner
    banner = Image.new('RGBA', (banner_width, banner_height), background_color)
    
    # Place logos horizontally
    for i, logo in enumerate(rounded_logos):
        x = i * (logo_size[0] + spacing)
        y = 0
        banner.paste(logo, (x, y), logo)
    
    # Save banner
    banner.save(output_path, "PNG")
    print(f"🎉 Created storage banner: {output_path}")
    print(f"   Size: {banner_width}x{banner_height}px")
    print(f"   Logos: {logos_count}")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Create storage banner for ABI")
    parser.add_argument("--assets-dir", default="assets", help="Assets directory")
    parser.add_argument("--output", default="assets/storage-banner.png", help="Output file")
    parser.add_argument("--size", type=int, default=80, help="Logo size (square)")
    parser.add_argument("--spacing", type=int, default=20, help="Spacing between logos")
    parser.add_argument("--transparent", action="store_true", help="Transparent background")
    
    args = parser.parse_args()
    
    logo_size = (args.size, args.size)
    bg_color = (255, 255, 255, 0) if args.transparent else (255, 255, 255, 255)
    
    success = create_storage_banner(
        assets_dir=args.assets_dir,
        output_path=args.output,
        logo_size=logo_size,
        spacing=args.spacing,
        background_color=bg_color
    )
    
    if success:
        print(f"\n🚀 Usage in README:")
        print(f'<img src="{args.output}" alt="Storage Technologies" width="300">')
    else:
        print("❌ Failed to create banner")

if __name__ == "__main__":
    main()

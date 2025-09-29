#!/usr/bin/env python3
"""
Script to create a banner with rounded domain expert logos for ABI README
Generates a horizontal banner with domain expert avatars side by side
"""

from PIL import Image, ImageDraw
import os
import argparse
from pathlib import Path

# Core domain experts (in preferred order)
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
    "inside-sales representative.png"
]

def create_rounded_image(img_path, size=(60, 60), radius_percent=0.25):
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

def create_domain_experts_banner(
    assets_dir="assets/domain-experts",
    output_path="assets/domain-experts-banner.png", 
    logo_size=(80, 80),  # Standard ABI banner size
    spacing=20,          # Standard ABI banner spacing  
    max_per_row=8,
    background_color=(255, 255, 255, 0)  # Transparent
):
    """
    Create a banner with domain expert logos arranged in rows
    
    Args:
        assets_dir: Directory containing domain expert logo files
        output_path: Where to save the banner
        logo_size: Size of each logo (width, height)
        spacing: Pixels between logos
        max_per_row: Maximum logos per row
        background_color: RGBA background color
    """
    assets_path = Path(assets_dir)
    
    # Find available domain expert logos
    available_logos = []
    for expert_file in DOMAIN_EXPERTS:
        logo_path = assets_path / expert_file
        if logo_path.exists():
            available_logos.append(logo_path)
        else:
            print(f"⚠️  Logo not found: {logo_path}")
    
    if not available_logos:
        print("❌ No domain expert logos found!")
        return False
    
    print(f"🎯 Found {len(available_logos)} domain expert logos")
    
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
    print(f"🎉 Created domain experts banner: {output_path}")
    print(f"   Size: {banner_width}x{banner_height}px")
    print(f"   Experts: {logos_count} ({rows} rows)")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Create domain experts banner for ABI README")
    parser.add_argument("--assets-dir", default="assets/domain-experts", help="Domain experts assets directory")
    parser.add_argument("--output", default="assets/domain-experts-banner.png", help="Output file")
    parser.add_argument("--size", type=int, default=80, help="Logo size (square) - Standard ABI banner size")
    parser.add_argument("--spacing", type=int, default=20, help="Spacing between logos - Standard ABI banner spacing")
    parser.add_argument("--per-row", type=int, default=8, help="Max logos per row")
    parser.add_argument("--transparent", action="store_true", help="Transparent background")
    
    args = parser.parse_args()
    
    logo_size = (args.size, args.size)
    bg_color = (255, 255, 255, 0) if args.transparent else (255, 255, 255, 255)
    
    success = create_domain_experts_banner(
        assets_dir=args.assets_dir,
        output_path=args.output,
        logo_size=logo_size,
        spacing=args.spacing,
        max_per_row=args.per_row,
        background_color=bg_color
    )
    
    if success:
        print(f"\n🚀 Usage in README:")
        print(f'<img src="{args.output}" alt="Domain Expert Agents" width="500">')
    else:
        print("❌ Failed to create banner")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Script to create a banner with rounded LLM logos for ABI README
Generates a horizontal banner with AI model logos side by side
"""

from PIL import Image, ImageDraw
import os
import argparse
from pathlib import Path

# Core LLM logos (in preferred order)
CORE_LLMS = [
    "chatgpt.jpg",
    "claude.png", 
    "gemini.png",
    "grok.jpg",
    "llama.jpeg",
    "mistral.png",
    "perplexity.png",
    "qwen.jpg",
    "deepseek.png",
    "gemma.png"
]

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

def create_llm_banner(
    assets_dir="assets",
    output_path="assets/llm-banner.png", 
    logo_size=(80, 80),  # Standard ABI banner size
    spacing=20,          # Standard ABI banner spacing
    max_per_row=5,
    background_color=(255, 255, 255, 0)  # Transparent
):
    """
    Create a banner with LLM logos arranged in rows
    
    Args:
        assets_dir: Directory containing logo files
        output_path: Where to save the banner
        logo_size: Size of each logo (width, height)
        spacing: Pixels between logos
        max_per_row: Maximum logos per row
        background_color: RGBA background color
    """
    assets_path = Path(assets_dir)
    
    # Find available LLM logos
    available_logos = []
    for llm_file in CORE_LLMS:
        logo_path = assets_path / llm_file
        if logo_path.exists():
            available_logos.append(logo_path)
        else:
            print(f"⚠️  Logo not found: {logo_path}")
    
    if not available_logos:
        print("❌ No LLM logos found!")
        return False
    
    print(f"🎯 Found {len(available_logos)} LLM logos")
    
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
    print(f"🎉 Created LLM banner: {output_path}")
    print(f"   Size: {banner_width}x{banner_height}px")
    print(f"   Logos: {logos_count} ({rows} rows)")
    
    return True

def main():
    parser = argparse.ArgumentParser(description="Create LLM banner for ABI README")
    parser.add_argument("--assets-dir", default="assets", help="Assets directory")
    parser.add_argument("--output", default="assets/llm-banner.png", help="Output file")
    parser.add_argument("--size", type=int, default=80, help="Logo size (square)")
    parser.add_argument("--spacing", type=int, default=20, help="Spacing between logos")
    parser.add_argument("--per-row", type=int, default=5, help="Max logos per row")
    parser.add_argument("--transparent", action="store_true", help="Transparent background")
    
    args = parser.parse_args()
    
    logo_size = (args.size, args.size)
    bg_color = (255, 255, 255, 0) if args.transparent else (255, 255, 255, 255)
    
    success = create_llm_banner(
        assets_dir=args.assets_dir,
        output_path=args.output,
        logo_size=logo_size,
        spacing=args.spacing,
        max_per_row=args.per_row,
        background_color=bg_color
    )
    
    if success:
        print(f"\n🚀 Usage in README:")
        print(f'<img src="{args.output}" alt="Supported AI Models" width="400">')
    else:
        print("❌ Failed to create banner")

if __name__ == "__main__":
    main()

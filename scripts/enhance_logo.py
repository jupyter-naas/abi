#!/usr/bin/env python3
"""
Script to enhance pixelated logos using PIL image processing
Applies upscaling, sharpening, and noise reduction techniques
"""

from PIL import Image, ImageFilter, ImageEnhance
import argparse
from pathlib import Path

def enhance_pixelated_logo(
    input_path,
    output_path,
    scale_factor=2,
    sharpen_factor=1.5,
    contrast_factor=1.1,
    color_factor=1.1
):
    """
    Enhance a pixelated logo using various PIL techniques
    
    Args:
        input_path: Path to input image
        output_path: Path to save enhanced image
        scale_factor: How much to upscale (2x, 3x, etc.)
        sharpen_factor: Sharpening intensity (1.0 = no change)
        contrast_factor: Contrast enhancement (1.0 = no change)
        color_factor: Color saturation enhancement (1.0 = no change)
    """
    try:
        # Open the original image
        img = Image.open(input_path).convert("RGBA")
        original_size = img.size
        
        print(f"📥 Original size: {original_size[0]}x{original_size[1]}px")
        
        # Step 1: Upscale using LANCZOS (high-quality resampling)
        new_size = (original_size[0] * scale_factor, original_size[1] * scale_factor)
        img_upscaled = img.resize(new_size, Image.Resampling.LANCZOS)
        print(f"🔍 Upscaled to: {new_size[0]}x{new_size[1]}px")
        
        # Step 2: Apply slight blur to reduce pixelation artifacts
        img_smooth = img_upscaled.filter(ImageFilter.GaussianBlur(radius=0.5))
        
        # Step 3: Enhance sharpness
        enhancer_sharp = ImageEnhance.Sharpness(img_smooth)
        img_sharp = enhancer_sharp.enhance(sharpen_factor)
        print(f"✨ Applied sharpening: {sharpen_factor}x")
        
        # Step 4: Enhance contrast
        enhancer_contrast = ImageEnhance.Contrast(img_sharp)
        img_contrast = enhancer_contrast.enhance(contrast_factor)
        print(f"🎨 Enhanced contrast: {contrast_factor}x")
        
        # Step 5: Enhance color saturation
        enhancer_color = ImageEnhance.Color(img_contrast)
        img_final = enhancer_color.enhance(color_factor)
        print(f"🌈 Enhanced colors: {color_factor}x")
        
        # Step 6: Apply unsharp mask for final crispness
        img_final = img_final.filter(ImageFilter.UnsharpMask(radius=1, percent=150, threshold=3))
        print(f"🔧 Applied unsharp mask")
        
        # Save the enhanced image
        img_final.save(output_path, "PNG", optimize=True)
        
        final_size = img_final.size
        print(f"💾 Saved enhanced logo: {output_path}")
        print(f"📏 Final size: {final_size[0]}x{final_size[1]}px")
        
        return True
        
    except Exception as e:
        print(f"❌ Error enhancing image: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="Enhance pixelated logos using PIL")
    parser.add_argument("input", help="Input image path")
    parser.add_argument("output", help="Output image path")
    parser.add_argument("--scale", type=int, default=2, help="Scale factor (default: 2)")
    parser.add_argument("--sharpen", type=float, default=1.5, help="Sharpen factor (default: 1.5)")
    parser.add_argument("--contrast", type=float, default=1.1, help="Contrast factor (default: 1.1)")
    parser.add_argument("--color", type=float, default=1.1, help="Color saturation factor (default: 1.1)")
    
    args = parser.parse_args()
    
    success = enhance_pixelated_logo(
        input_path=args.input,
        output_path=args.output,
        scale_factor=args.scale,
        sharpen_factor=args.sharpen,
        contrast_factor=args.contrast,
        color_factor=args.color
    )
    
    if success:
        print(f"\n🎉 Enhancement complete!")
        print(f"Original: {args.input}")
        print(f"Enhanced: {args.output}")
    else:
        print("❌ Enhancement failed")

if __name__ == "__main__":
    main()

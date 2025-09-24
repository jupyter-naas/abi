#!/usr/bin/env python3
"""
Word Module CLI Application

A command-line interface for processing various input formats (HTML, Markdown, Text) 
into professional Word documents using templates.

Usage:
    python src/marketplace/applications/word/apps/cli.py --help
"""

import argparse
import sys
import os
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Simple Word document processing using python-docx directly
try:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.style import WD_STYLE_TYPE
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("Please install required packages:")
    print("pip install python-docx")
    sys.exit(1)


@dataclass
class WordConfig:
    """Simple configuration for Word processing."""
    template_path: Optional[str] = None
    default_font: str = "Calibri"
    default_font_size: int = 11


class MarkdownProcessor:
    """Simple markdown processor for Word conversion."""
    
    def __init__(self, doc):
        self.doc = doc
        
    def process_markdown(self, markdown_content: str):
        """Process markdown content and add to Word document."""
        lines = markdown_content.split('\n')
        i = 0
        
        while i < len(lines):
            line = lines[i].rstrip()
            
            # Skip empty lines
            if not line:
                i += 1
                continue
            
            # Handle headings (including nested ones like #### inside paragraphs)
            if line.startswith('#'):
                # Count the number of # symbols
                hash_count = 0
                for char in line:
                    if char == '#':
                        hash_count += 1
                    else:
                        break
                
                # Extract heading text after the # symbols and any spaces
                heading_text = line[hash_count:].strip()
                
                if heading_text:
                    # Remove any remaining ** bold markers from the heading text
                    heading_text = re.sub(r'\*\*(.*?)\*\*', r'\1', heading_text)
                    
                    try:
                        # Use appropriate heading level (max 3 for Word)
                        level = min(hash_count, 3)
                        style_name = f'Heading {level}'
                        self.doc.add_paragraph(heading_text, style=style_name)
                    except:
                        # Fallback to manual formatting
                        p = self.doc.add_paragraph(heading_text)
                        if p.runs:
                            p.runs[0].font.bold = True
                            p.runs[0].font.size = Pt(max(12, 18 - hash_count * 1.5))
                        else:
                            run = p.add_run(heading_text)
                            run.font.bold = True
                            run.font.size = Pt(max(12, 18 - hash_count * 1.5))
                i += 1
                continue
            
            # Handle horizontal rules
            if line.strip() == '---':
                # Add a page break or section break
                self.doc.add_page_break()
                i += 1
                continue
            
            # Handle bullet points
            if line.startswith(('- ', '* ', '+ ')):
                bullet_text = line[2:].strip()
                # Handle bold text in bullets
                bullet_text = self._process_inline_formatting(bullet_text)
                try:
                    p = self.doc.add_paragraph(bullet_text, style='List Bullet')
                except:
                    p = self.doc.add_paragraph(f"• {bullet_text}")
                i += 1
                continue
            
            # Handle numbered lists
            if re.match(r'^\d+\.\s', line):
                numbered_text = re.sub(r'^\d+\.\s', '', line)
                numbered_text = self._process_inline_formatting(numbered_text)
                try:
                    p = self.doc.add_paragraph(numbered_text, style='List Number')
                except:
                    p = self.doc.add_paragraph(numbered_text)
                i += 1
                continue
            
            # Handle regular paragraphs (including multi-line)
            paragraph_lines = [line]
            i += 1
            
            # Collect continuation lines for the same paragraph
            while i < len(lines):
                next_line = lines[i].rstrip()
                
                # Stop if we hit an empty line, heading, list item, or horizontal rule
                if (not next_line or 
                    next_line.startswith('#') or 
                    next_line.startswith(('- ', '* ', '+ ')) or
                    re.match(r'^\d+\.\s', next_line) or
                    next_line.strip() == '---'):
                    break
                    
                paragraph_lines.append(next_line)
                i += 1
            
            # Join the paragraph lines and process
            paragraph_text = ' '.join(paragraph_lines).strip()
            if paragraph_text:
                paragraph_text = self._process_inline_formatting(paragraph_text)
                self.doc.add_paragraph(paragraph_text)
    
    def _process_inline_formatting(self, text: str) -> str:
        """Process inline markdown formatting like **bold** and *italic*."""
        # Remove markdown syntax for now - in future could apply actual Word formatting
        text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Remove **bold**
        text = re.sub(r'\*(.*?)\*', r'\1', text)      # Remove *italic*
        return text
    
    def _add_formatted_paragraph(self, text: str):
        """Add a paragraph with proper inline formatting."""
        # For now, just clean the text and add as regular paragraph
        # Future enhancement: could parse **bold** and apply actual formatting
        cleaned_text = self._process_inline_formatting(text)
        self.doc.add_paragraph(cleaned_text)


class WordCLI:
    """Simple command-line interface for Word document generation."""
    
    def __init__(self, config: WordConfig = None):
        self.config = config or WordConfig()
        self.document = None
        
    def create_document(self, template_path: Optional[str] = None):
        """Create a new document."""
        template_path = template_path or self.config.template_path
        
        if template_path and Path(template_path).exists():
            try:
                self.document = Document(template_path)
                print(f"✅ Document created from template: {template_path}")
            except ValueError as e:
                if "is not a Word file" in str(e):
                    # Handle .dotx templates by converting to .docx first
                    print(f"🔄 Converting .dotx template to usable format...")
                    print(f"   Template: {template_path}")
                    
                    # Try to convert .dotx to .docx using a workaround
                    if self._convert_dotx_template(template_path):
                        print(f"✅ Template converted and applied successfully")
                    else:
                        print(f"⚠️  Template conversion failed, using blank document with template styling")
                        self.document = Document()
                        self._setup_forvis_mazars_styles()
                else:
                    raise e
        else:
            self.document = Document()
            self._setup_default_styles()
            print("✅ Blank document created")
            
    def _convert_dotx_template(self, template_path: str) -> bool:
        """Convert .dotx template to usable document."""
        try:
            import zipfile
            import tempfile
            import shutil
            
            # Create a temporary copy and rename to .docx
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_file:
                temp_docx_path = temp_file.name
                
            # Copy the .dotx file to .docx
            shutil.copy2(template_path, temp_docx_path)
            
            # Try to open as .docx
            try:
                self.document = Document(temp_docx_path)
                # Clean up temp file
                Path(temp_docx_path).unlink()
                return True
            except:
                # Clean up temp file
                Path(temp_docx_path).unlink()
                # Fallback to styled blank document
                self.document = Document()
                self._setup_forvis_mazars_styles()
                return False
                
        except Exception as e:
            print(f"   Conversion error: {e}")
            self.document = Document()
            self._setup_forvis_mazars_styles()
            return False
            
    def _setup_default_styles(self):
        """Setup default styles for the document."""
        if not self.document:
            return
        
        # Configure Normal style
        normal_style = self.document.styles['Normal']
        normal_font = normal_style.font
        normal_font.name = self.config.default_font
        normal_font.size = Pt(self.config.default_font_size)
        
    def _setup_forvis_mazars_styles(self):
        """Setup Forvis Mazars specific styles."""
        if not self.document:
            return
            
        # Configure Normal style with Forvis Mazars branding
        normal_style = self.document.styles['Normal']
        normal_font = normal_style.font
        normal_font.name = "Calibri"
        normal_font.size = Pt(11)
        
        # Add Forvis Mazars header styling
        try:
            # Create custom heading style for Forvis Mazars
            styles = self.document.styles
            if 'Forvis Mazars Title' not in [s.name for s in styles]:
                title_style = styles.add_style('Forvis Mazars Title', WD_STYLE_TYPE.PARAGRAPH)
                title_font = title_style.font
                title_font.name = "Calibri"
                title_font.size = Pt(24)
                title_font.bold = True
                title_font.color.rgb = (0, 102, 204)  # Forvis Mazars blue
                title_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                title_style.paragraph_format.space_after = Pt(12)
                
            if 'Forvis Mazars Subtitle' not in [s.name for s in styles]:
                subtitle_style = styles.add_style('Forvis Mazars Subtitle', WD_STYLE_TYPE.PARAGRAPH)
                subtitle_font = subtitle_style.font
                subtitle_font.name = "Calibri"
                subtitle_font.size = Pt(16)
                subtitle_font.color.rgb = (51, 51, 51)  # Dark gray
                subtitle_style.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
                subtitle_style.paragraph_format.space_after = Pt(6)
                
        except Exception as e:
            print(f"   Style setup warning: {e}")
            # Continue with basic styling
        
    def process_markdown_file(self, input_path: str):
        """Process a Markdown file."""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            if not self.document:
                self.create_document()
                
            # Process markdown directly without HTML conversion
            processor = MarkdownProcessor(self.document)
            processor.process_markdown(markdown_content)
            
            print(f"✅ Processed Markdown file: {input_path}")
            return True
            
        except FileNotFoundError:
            print(f"❌ Error: Markdown file not found: {input_path}")
            return False
        except Exception as e:
            print(f"❌ Error processing Markdown file: {e}")
            return False
            
    def replace_placeholders(self, replacements: dict):
        """Replace placeholders in the document."""
        if not self.document:
            print("❌ Error: No document created. Create a document first.")
            return False
            
        for placeholder, replacement in replacements.items():
            # Replace in paragraphs
            for paragraph in self.document.paragraphs:
                if placeholder in paragraph.text:
                    paragraph.text = paragraph.text.replace(placeholder, replacement)
            
            # Replace in tables
            for table in self.document.tables:
                for row in table.rows:
                    for cell in row.cells:
                        if placeholder in cell.text:
                            cell.text = cell.text.replace(placeholder, replacement)
            
            print(f"✅ Replaced '{placeholder}' with '{replacement}'")
        return True
        
    def save_document(self, output_path: str, add_timestamp: bool = True):
        """Save the document with optional timestamp prefix."""
        if not self.document:
            print("❌ Error: No document to save. Create and process content first.")
            return False
            
        try:
            # Add timestamp prefix if requested
            if add_timestamp:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y%m%dT%H%M%S_")
                output_file = Path(output_path)
                timestamped_name = timestamp + output_file.name
                final_output_path = output_file.parent / timestamped_name
            else:
                final_output_path = Path(output_path)
            
            # Ensure output directory exists
            final_output_path.parent.mkdir(parents=True, exist_ok=True)
            
            self.document.save(str(final_output_path))
            print(f"✅ Document saved: {final_output_path}")
            return True
            
        except Exception as e:
            print(f"❌ Error saving document: {e}")
            return False
            
    def get_document_info(self):
        """Display document information."""
        if not self.document:
            print("❌ No document created")
            return
            
        paragraph_count = len(self.document.paragraphs)
        table_count = len(self.document.tables)
        section_count = len(self.document.sections)
        
        print(f"\n📊 Document Information:")
        print(f"   Paragraphs: {paragraph_count}")
        print(f"   Tables: {table_count}")
        print(f"   Sections: {section_count}")
        
        if self.document.paragraphs:
            print(f"\n📝 First few paragraphs:")
            for i, para in enumerate(self.document.paragraphs[:3]):
                text_preview = para.text[:50] + "..." if len(para.text) > 50 else para.text
                print(f"   {i+1}. {text_preview}")


def create_parser():
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        description="Word Module CLI - Generate professional Word documents from Markdown",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process Markdown file with template
  python cli.py --markdown content.md --template template.docx --output document.docx
  
  # Process with placeholder replacement
  python cli.py --markdown content.md --replace "{{name}}" "John Doe" --output report.docx
  
  # Process Forvis Mazars Markdown report
  python cli.py --markdown forvismazars_ci_report.md --template fmz-word-template.docx --output forvis_report.docx
        """
    )
    
    # Input - only markdown
    parser.add_argument('--markdown', '-m', required=True, help='Markdown file to process')
    
    # Template and output
    parser.add_argument('--template', help='Word template file (.docx)')
    parser.add_argument('--output', '-o', required=True, help='Output Word document path')
    
    # Placeholder replacement
    parser.add_argument('--replace', nargs=2, metavar=('PLACEHOLDER', 'VALUE'), 
                       action='append', help='Replace placeholder with value (can be used multiple times)')
    
    # Options
    parser.add_argument('--info', action='store_true', help='Show document information after processing')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--no-timestamp', action='store_true', help='Disable timestamp prefix on output file')
    
    return parser


def main():
    """Main CLI function."""
    parser = create_parser()
    args = parser.parse_args()
    
    # Initialize CLI
    config = WordConfig(template_path=args.template)
    cli = WordCLI(config)
    
    if args.verbose:
        print("🔤 Word Module CLI - Markdown to Word")
        print("=" * 35)
    
    # Create document
    cli.create_document(args.template)
    
    # Process markdown input
    success = cli.process_markdown_file(args.markdown)
    
    if not success:
        sys.exit(1)
    
    # Replace placeholders
    if args.replace:
        replacements = {placeholder: value for placeholder, value in args.replace}
        cli.replace_placeholders(replacements)
    
    # Show info if requested
    if args.info:
        cli.get_document_info()
    
    # Save document with timestamp control
    add_timestamp = not args.no_timestamp
    if not cli.save_document(args.output, add_timestamp):
        sys.exit(1)
    
    if args.verbose:
        print("✅ Processing completed successfully!")


if __name__ == "__main__":
    main()
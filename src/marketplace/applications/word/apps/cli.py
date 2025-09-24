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
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Simple Word document processing using python-docx directly
try:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.style import WD_STYLE_TYPE
    import markdown
    from html.parser import HTMLParser
except ImportError as e:
    print(f"❌ Missing dependencies: {e}")
    print("Please install required packages:")
    print("pip install python-docx markdown")
    sys.exit(1)


@dataclass
class WordConfig:
    """Simple configuration for Word processing."""
    template_path: Optional[str] = None
    default_font: str = "Calibri"
    default_font_size: int = 11


class SimpleHTMLParser(HTMLParser):
    """Enhanced HTML parser for Word conversion with template style support."""
    
    def __init__(self, doc):
        super().__init__()
        self.doc = doc
        self.current_text = ""
        self.in_heading = False
        self.heading_level = 1
        self.skip_tags = {'style', 'script', 'head', 'meta', 'title'}
        self.current_tag = None
        self.preserve_all_content = True  # Don't truncate sources
        self.template_styles = self._get_template_styles()
        
    def _get_template_styles(self):
        """Get available styles from the template."""
        styles = {}
        try:
            for style in self.doc.styles:
                styles[style.name.lower()] = style.name
        except:
            pass
        return styles
        
    def _get_best_style(self, content_type):
        """Get the best matching style from template."""
        content_lower = content_type.lower()
        
        # Try to match template styles
        for template_style_key, template_style_name in self.template_styles.items():
            if any(keyword in template_style_key for keyword in ['title', 'heading', 'header']) and 'title' in content_lower:
                return template_style_name
            elif any(keyword in template_style_key for keyword in ['subtitle', 'sub']) and 'subtitle' in content_lower:
                return template_style_name
            elif any(keyword in template_style_key for keyword in ['body', 'normal', 'text']) and 'body' in content_lower:
                return template_style_name
                
        # Fallback to standard styles
        if 'title' in content_lower:
            return 'Title' if 'Title' in [s.name for s in self.doc.styles] else None
        elif 'subtitle' in content_lower:
            return 'Subtitle' if 'Subtitle' in [s.name for s in self.doc.styles] else None
        elif 'heading' in content_lower:
            return f'Heading {min(self.heading_level, 3)}'
            
        return None
        
    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag in self.skip_tags:
            return
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            self.in_heading = True
            self.heading_level = int(tag[1])
        elif tag == 'br':
            self.current_text += '\n'
        elif tag == 'div':
            # Check for special div classes that might indicate content type
            class_attr = dict(attrs).get('class', '')
            if 'header' in class_attr:
                self.current_tag = 'header'
            elif 'title' in class_attr:
                self.current_tag = 'title'
            elif 'subtitle' in class_attr:
                self.current_tag = 'subtitle'
            
    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            return
            
        if tag in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
            if self.current_text.strip():
                # Try to use template heading style
                style_name = self._get_best_style('heading')
                if style_name:
                    try:
                        p = self.doc.add_paragraph(self.current_text.strip(), style=style_name)
                    except:
                        p = self.doc.add_paragraph(self.current_text.strip())
                        run = p.runs[0] if p.runs else p.add_run(self.current_text.strip())
                        run.font.bold = True
                        run.font.size = Pt(18 - self.heading_level * 2)
                else:
                    p = self.doc.add_paragraph(self.current_text.strip())
                    run = p.runs[0] if p.runs else p.add_run(self.current_text.strip())
                    run.font.bold = True
                    run.font.size = Pt(18 - self.heading_level * 2)
            self.current_text = ""
            self.in_heading = False
            
        elif tag in ['p', 'div']:
            if self.current_text.strip():
                # Determine content type and use appropriate template style
                content = self.current_text.strip()
                style_name = None
                
                # Check if this looks like a title or subtitle
                if any(keyword in content.lower() for keyword in ['competitive intelligence', 'report']):
                    style_name = self._get_best_style('title')
                elif any(keyword in content.lower() for keyword in ['week of', 'prepared:']):
                    style_name = self._get_best_style('subtitle')
                else:
                    style_name = self._get_best_style('body')
                
                # Add paragraph with template style
                if style_name:
                    try:
                        self.doc.add_paragraph(content, style=style_name)
                    except:
                        self.doc.add_paragraph(content)
                else:
                    self.doc.add_paragraph(content)
                    
            self.current_text = ""
            
    def handle_data(self, data):
        if self.current_tag in self.skip_tags:
            return
            
        # Preserve ALL content including sources - don't truncate
        if data.strip():
            if self.current_text and not self.current_text.endswith(' ') and not data.startswith(' '):
                self.current_text += ' '
            self.current_text += data.strip()
    
    def close(self):
        # Ensure any remaining content is added
        if self.current_text.strip():
            self.doc.add_paragraph(self.current_text.strip())
        super().close()


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
        
    def process_html_file(self, input_path: str):
        """Process an HTML file."""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            if not self.document:
                self.create_document()
                
            parser = SimpleHTMLParser(self.document)
            parser.feed(html_content)
            parser.close()
            
            print(f"✅ Processed HTML file: {input_path}")
            return True
            
        except FileNotFoundError:
            print(f"❌ Error: HTML file not found: {input_path}")
            return False
        except Exception as e:
            print(f"❌ Error processing HTML file: {e}")
            return False
            
    def process_markdown_file(self, input_path: str):
        """Process a Markdown file."""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                markdown_content = f.read()
            
            if not self.document:
                self.create_document()
                
            # Convert markdown to HTML then process
            html_content = markdown.markdown(markdown_content)
            parser = SimpleHTMLParser(self.document)
            parser.feed(html_content)
            parser.close()
            
            print(f"✅ Processed Markdown file: {input_path}")
            return True
            
        except FileNotFoundError:
            print(f"❌ Error: Markdown file not found: {input_path}")
            return False
        except Exception as e:
            print(f"❌ Error processing Markdown file: {e}")
            return False
            
    def process_text_file(self, input_path: str):
        """Process a plain text file."""
        try:
            with open(input_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
            
            if not self.document:
                self.create_document()
                
            # Simple text processing
            lines = text_content.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                    
                # Detect headings
                if line.startswith('#'):
                    level = len(line) - len(line.lstrip('#'))
                    heading_text = line.lstrip('# ').strip()
                    p = self.document.add_paragraph(heading_text)
                    run = p.runs[0] if p.runs else p.add_run(heading_text)
                    run.font.bold = True
                    run.font.size = Pt(18 - level * 2)
                else:
                    self.document.add_paragraph(line)
            
            print(f"✅ Processed text file: {input_path}")
            return True
            
        except FileNotFoundError:
            print(f"❌ Error: Text file not found: {input_path}")
            return False
        except Exception as e:
            print(f"❌ Error processing text file: {e}")
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
        description="Word Module CLI - Generate professional Word documents from various input formats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process HTML with template
  python cli.py --html input.html --template template.docx --output report.docx
  
  # Process Markdown file
  python cli.py --markdown content.md --output document.docx
  
  # Process with placeholder replacement
  python cli.py --html input.html --replace "{{name}}" "John Doe" --output report.docx
  
  # Process Forvis Mazars HTML
  python cli.py --html storage/datastore/marketplace/applications/word/inputs/forvismazars_ci_docx.html --template "storage/datastore/marketplace/applications/word/templates/Forvis Mazars_Word Template Portrait_blank.dotx" --output forvis_report.docx
        """
    )
    
    # Input options
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument('--html', help='HTML file to process')
    input_group.add_argument('--markdown', '-m', help='Markdown file to process')
    input_group.add_argument('--text', '-t', help='Text file to process')
    
    # Template and output
    parser.add_argument('--template', help='Word template file (.docx/.dotx)')
    parser.add_argument('--output', '-o', help='Output Word document path')
    
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
    
    # Validate arguments
    if not any([args.html, args.markdown, args.text]):
        print("❌ Error: Please specify an input file (--html, --markdown, or --text)")
        parser.print_help()
        sys.exit(1)
    
    if not args.output:
        print("❌ Error: Please specify an output file with --output")
        sys.exit(1)
    
    # Initialize CLI
    config = WordConfig(template_path=args.template)
    cli = WordCLI(config)
    
    if args.verbose:
        print("🔤 Word Module CLI")
        print("=" * 20)
    
    # Create document
    cli.create_document(args.template)
    
    # Process input
    success = False
    if args.html:
        success = cli.process_html_file(args.html)
    elif args.markdown:
        success = cli.process_markdown_file(args.markdown)
    elif args.text:
        success = cli.process_text_file(args.text)
    
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
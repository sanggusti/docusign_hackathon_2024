import io
import re  # Add missing import
from typing import Union, Dict
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER

class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_styles()

    def _setup_styles(self):
        """Setup custom styles for PDF generation"""
        # Add custom styles
        self.styles.add(
            ParagraphStyle(
                name='CustomTitle',
                parent=self.styles['Heading1'],
                fontSize=24,
                spaceAfter=30,
                alignment=TA_CENTER,
                textColor='navy'
            )
        )
        
        # Add SectionHeader style
        self.styles.add(
            ParagraphStyle(
                name='SectionHeader',
                parent=self.styles['Heading2'],
                fontSize=16,
                spaceBefore=20,
                spaceAfter=12,
                textColor='navy',
                alignment=TA_LEFT
            )
        )
        
        self.styles.add(
            ParagraphStyle(
                name='CustomContent',
                parent=self.styles['Normal'],
                fontSize=12,
                spaceAfter=12,
                alignment=TA_LEFT,
                leading=16
            )
        )

    def generate_pdf(self, content: Union[str, Dict]) -> io.BytesIO:
        """Generate PDF with improved formatting"""
        try:
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer, 
                pagesize=letter,
                rightMargin=72,
                leftMargin=72,
                topMargin=72,
                bottomMargin=72
            )
            elements = []

            # Process title and content
            if isinstance(content, dict):
                title = content.get('title', 'Medical Document')
                content_text = content.get('content', '')
                if isinstance(content_text, dict):
                    content_text = json.dumps(content_text, indent=2)
            else:
                title = "Medical Document"
                content_text = str(content)

            # Add title
            elements.append(Paragraph(title, self.styles['CustomTitle']))
            elements.append(Spacer(1, 20))

            # Process content sections
            sections = content_text.split('\n')
            for section in sections:
                if section.strip():
                    # Check if this is a header
                    if section.startswith('##') or section.startswith('# '):
                        header_text = section.lstrip('#').strip()
                        elements.append(Paragraph(header_text, self.styles['SectionHeader']))
                        elements.append(Spacer(1, 12))
                    else:
                        # Handle bullet points and regular text
                        if section.strip().startswith('-'):
                            text = '•' + section.strip()[1:]
                        else:
                            text = section.strip()
                        elements.append(Paragraph(text, self.styles['CustomContent']))
                        elements.append(Spacer(1, 8))

            # Build PDF
            doc.build(elements)
            buffer.seek(0)
            return buffer

        except Exception as e:
            print(f"PDF Generation error: {str(e)}")
            # Create error PDF
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = [
                Paragraph("Error Generating Document", self.styles['CustomTitle']),
                Spacer(1, 12),
                Paragraph(f"An error occurred: {str(e)}", self.styles['CustomContent'])
            ]
            doc.build(elements)
            buffer.seek(0)
            return buffer

    def _format_content(self, content: Union[str, Dict]) -> str:
        """Format content for PDF generation"""
        if isinstance(content, str):
            return content
        elif isinstance(content, dict):
            try:
                # Handle nested content
                if 'content' in content:
                    return self._format_content(content['content'])
                # Format dictionary as string
                return "\n".join(f"{k}: {v}" for k, v in content.items())
            except Exception as e:
                return f"Error formatting content: {str(e)}"
        else:
            return str(content)

if __name__ == "__main__":
    # Test the PDF generator
    pdf_gen = PDFGenerator()
    
    # Test with string
    test_str = "This is a test document\nWith multiple lines\nAnd some content."
    pdf_bytes = pdf_gen.generate_pdf(test_str)
    
    # Test with dictionary
    test_dict = {
        "title": "Test Document",
        "content": "This is the content of the test document."
    }
    pdf_bytes = pdf_gen.generate_pdf(test_dict)
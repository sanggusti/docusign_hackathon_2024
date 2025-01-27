import io
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
        # Check if styles already exist before adding
        if 'CustomTitle' not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name='CustomTitle',
                    parent=self.styles['Heading1'],
                    fontSize=16,
                    spaceAfter=30,
                    alignment=TA_CENTER
                )
            )
        if 'CustomContent' not in self.styles:
            self.styles.add(
                ParagraphStyle(
                    name='CustomContent',
                    parent=self.styles['Normal'],
                    fontSize=12,
                    spaceAfter=12,
                    alignment=TA_LEFT
                )
            )

    def generate_pdf(self, content: Union[str, Dict]) -> io.BytesIO:
        """Generate PDF from content string or dictionary"""
        try:
            # Create buffer
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=letter)
            elements = []

            # Process title
            if isinstance(content, dict):
                title = content.get('title', 'Document')
                if isinstance(content.get('content'), (str, dict)):
                    body = str(content.get('content'))
                else:
                    body = "No content available"
            else:
                title = "Document"
                body = str(content)

            # Add title
            elements.append(Paragraph(title, self.styles['CustomTitle']))
            elements.append(Spacer(1, 12))

            # Add content paragraphs
            for paragraph in body.split('\n'):
                if paragraph.strip():
                    elements.append(Paragraph(paragraph, self.styles['CustomContent']))
                    elements.append(Spacer(1, 12))

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
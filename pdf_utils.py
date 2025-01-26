# import reportlab
from io import BytesIO
from typing import Dict
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak
)

# create pdf
# init variables (doctemplate, styles, story)
# Append lines
# build
# return
class PDFGenerator:
    def __init__(self):
        self.styles = getSampleStyleSheet()
        
    def _create_header(self, title: str):
        return Paragraph(f"<b>{title}</b>", self.styles["Title"])
    
    def _create_section(self, title: str, content):
        elements = [
            Paragraph(f"<b>{title}</b>", self.styles["Heading2"]),
            Spacer(1, 12)
        ]
        
        if isinstance(content, list):
            for item in content:
                elements.append(Paragraph(f"• {item}", self.styles["BodyText"]))
        else:
            elements.append(Paragraph(content, self.styles["BodyText"]))
            
        elements.append(Spacer(1, 24))
        return elements
    
    def generate_pdf(self, document: Dict) -> BytesIO:
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []
        
        # Document Header
        elements.append(self._create_header(document["title"]))
        elements.append(Spacer(1, 24))
        
        # Patient Information
        elements += self._create_section(
            "Patient Information",
            document["content"]["patient_info"]
        )
        
        # Medical Details
        elements += self._create_section(
            "Medical Details",
            document["content"]["medical_details"]
        )
        
        # Insurance Information
        if "insurance" in document["content"]:
            elements += self._create_section(
                "Insurance Details",
                document["content"]["insurance"]
            )
            
        # Prescription Information
        if "prescription" in document["content"]:
            elements.append(PageBreak())
            elements += self._create_section(
                "Prescription",
                document["content"]["prescription"]
            )
        
        # Signature Block
        elements.append(self._create_signature_table())
        
        doc.build(elements)
        buffer.seek(0)
        return buffer
    
    def _create_signature_table(self):
        data = [
            ["Provider Signature:", "__________________________"],
            ["Date:", "__________________________"]
        ]
        
        table = Table(data, colWidths=[120, 300])
        table.setStyle(TableStyle([
            ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
            ("FONTSIZE", (0,0), (-1,-1), 12),
            ("BOTTOMPADDING", (0,0), (-1,-1), 12),
        ]))
        return table
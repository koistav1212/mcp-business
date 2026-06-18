import os
from typing import Optional, Type
from pydantic import BaseModel
from tools.base import BaseTool
from storage.local import local_storage
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

class CreatePDFInput(BaseModel):
    filename: str
    title: str
    body_text: str

class CreatePDFTool(BaseTool):
    name: str = "create_pdf"
    description: str = "Generates a beautifully typeset PDF document from text paragraphs."
    args_schema: Optional[Type[BaseModel]] = CreatePDFInput

    async def execute(self, **kwargs) -> str:
        filename = kwargs["filename"]
        if not filename.endswith(".pdf"):
            filename += ".pdf"
            
        title_text = kwargs["title"]
        body_text = kwargs["body_text"]

        # Temporary file location in the current workspace directory
        temp_path = f"temp_gen_{filename}"
        
        doc = SimpleDocTemplate(
            temp_path,
            pagesize=letter,
            rightMargin=54,
            leftMargin=54,
            topMargin=54,
            bottomMargin=54
        )

        styles = getSampleStyleSheet()
        
        # Color palette
        primary_color = colors.HexColor("#1e293b")  # Dark Slate
        text_color = colors.HexColor("#334155")     # Slate Grey

        title_style = ParagraphStyle(
            'PDFTitle',
            parent=styles['Heading1'],
            fontName='Helvetica-Bold',
            fontSize=22,
            leading=26,
            textColor=primary_color,
            spaceAfter=15
        )
        
        body_style = ParagraphStyle(
            'PDFBody',
            parent=styles['Normal'],
            fontName='Helvetica',
            fontSize=10,
            leading=15,
            textColor=text_color,
            spaceAfter=12
        )

        story = []
        story.append(Paragraph(title_text, title_style))
        story.append(Spacer(1, 10))

        # Split content into paragraphs to format correctly
        paragraphs = body_text.split("\n\n")
        for p in paragraphs:
            cleaned_p = p.strip().replace("\n", "<br/>")
            if cleaned_p:
                story.append(Paragraph(cleaned_p, body_style))
                story.append(Spacer(1, 6))

        doc.build(story)

        # Load file bytes and remove temp file
        with open(temp_path, "rb") as f:
            content = f.read()
            
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Save to local storage and retrieve URL
        download_url = local_storage.write_content(filename, content, "pdf")
        return download_url

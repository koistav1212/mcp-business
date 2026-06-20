import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from main import app
from tools.create_pdf import CreatePDFTool
from tools.create_ppt import CreatePPTTool
from connectors.gmail.actions import GmailConnector
from connectors.google_drive.actions import GoogleDriveConnector
from connectors.qdrant.client import QdrantConnector
from storage.local import local_storage

client = TestClient(app)

def test_storage_write():
    filename = "test_write.txt"
    content = b"hello operational agents"
    url = local_storage.write_content(filename, content, "docs")
    assert "/docs/test_write.txt" in url
    
    target_path = Path("artifacts/docs/test_write.txt")
    assert target_path.exists()
    assert target_path.read_bytes() == content

@pytest.mark.asyncio
async def test_pdf_tool():
    tool = CreatePDFTool()
    url = await tool.execute(
        filename="test_pdf.pdf",
        title="Test PDF Document",
        body_text="Hello, this is a test report lab document."
    )
    assert "/pdf/test_pdf.pdf" in url
    assert Path("artifacts/pdf/test_pdf.pdf").exists()

@pytest.mark.asyncio
async def test_ppt_tool():
    tool = CreatePPTTool()
    url = await tool.execute(
        filename="test_ppt.pptx",
        presentation_title="Test PowerPoint Title",
        slides=[
            {"title": "Slide 1 Title", "points": ["bullet 1", "bullet 2"]}
        ]
    )
    assert "/ppt/test_ppt.pptx" in url
    assert Path("artifacts/ppt/test_ppt.pptx").exists()

@pytest.mark.asyncio
async def test_qdrant_connector():
    qdrant = QdrantConnector()
    await qdrant.connect()
    upserted = await qdrant.upsert("doc1", "Zoho is a cloud software company.", {"company": "Zoho"})
    assert upserted is True
    
    search_results = await qdrant.search("Zoho software")
    assert len(search_results) == 1
    assert search_results[0]["id"] == "doc1"
    assert search_results[0]["score"] == 1.0

def test_proposal_writer_e2e():
    # Clear outbox first to verify sent email
    gmail = GmailConnector()
    gmail.get_outbox().clear()

    # 1. Create a session with Zoho query and custom email
    create_resp = client.post("/sessions", json={
        "query": "Write a proposal for Zoho and send it to director@zoho.com"
    })
    assert create_resp.status_code == 200
    session_id = create_resp.json()["session_id"]

    # 2. Execute the session plan
    exec_resp = client.post(f"/sessions/{session_id}/execute")
    assert exec_resp.status_code == 200
    result = exec_resp.json()

    assert result["status"] == "completed"
    assert result["metadata"]["routed_skill"] == "proposal-writer"
    assert result["verification"]["is_valid"] is True
    
    # 3. Check artifacts exist
    assert Path("artifacts/pdf/zoho_proposal.pdf").exists()
    assert Path("artifacts/ppt/zoho_slides.pptx").exists()

    # 4. Check outbox has the email sent to director@zoho.com
    outbox = gmail.get_outbox()
    assert len(outbox) >= 1
    sent_email = outbox[-1]
    assert sent_email["to"] == "director@zoho.com"
    assert "Briefing Deliverables for Zoho" in sent_email["subject"]
    assert "zoho_proposal.pdf" in sent_email["body"]
    assert "zoho_slides.pptx" in sent_email["body"]

@pytest.mark.asyncio
async def test_docs_tool():
    from tools.create_docs import CreateDocsTool
    tool = CreateDocsTool()
    url = await tool.execute(
        filename="test_docs.docx",
        title="Test Docs Document",
        body_text="Hello, this is a test Word document.",
        style="creative"
    )
    assert "/docs/test_docs.docx" in url
    assert Path("artifacts/docs/test_docs.docx").exists()

def test_generate_artifact_pdf_endpoint():
    resp = client.post("/workspace/generate-artifact", json={
        "company": "Zoho",
        "format": "pdf",
        "style": "minimalist",
        "prompt": "Focus on their tech stack and tools."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "pdf"
    assert "zoho_report_" in data["filename"]
    assert "/pdf/" in data["url"]
    assert Path(f"artifacts/pdf/{data['filename']}").exists()

def test_generate_artifact_ppt_endpoint():
    resp = client.post("/workspace/generate-artifact", json={
        "company": "Google",
        "format": "ppt",
        "style": "creative",
        "prompt": "Highlight marketing strategies and revenue numbers."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "ppt"
    assert "google_deck_" in data["filename"]
    assert "/ppt/" in data["url"]
    assert Path(f"artifacts/ppt/{data['filename']}").exists()

def test_generate_artifact_docs_endpoint():
    resp = client.post("/workspace/generate-artifact", json={
        "company": "Zoho",
        "format": "docs",
        "style": "professional",
        "prompt": "Include financial performance and founders."
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["format"] == "docs"
    assert "zoho_report_" in data["filename"]
    assert "/docs/" in data["url"]
    assert Path(f"artifacts/docs/{data['filename']}").exists()


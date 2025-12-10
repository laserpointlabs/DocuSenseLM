"""
Test document classification with real PDFs from the data folder.
This tests the actual classification workflow.
"""
import os
from pathlib import Path
import pytest
import sys

# Add python directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))


def test_classify_real_nda(mcp_servers):
    """Test classification of a real NDA document."""
    from python import server
    
    # Find an NDA PDF
    nda_dir = Path(__file__).parent.parent / "data" / "NDAs"
    if not nda_dir.exists():
        pytest.skip("NDA directory not found")
    
    nda_files = list(nda_dir.glob("*.pdf"))
    if not nda_files:
        pytest.skip("No NDA PDFs found")
    
    test_file = nda_files[0]
    print(f"\n📄 Testing classification of: {test_file.name}")
    
    # Set MCP URLs
    import os
    os.environ["MCP_OCR_URL"] = mcp_servers["ocr_url"]
    os.environ["MCP_RAG_URL"] = mcp_servers["rag_url"]
    
    # Classify the document
    doc_type = server.classify_doc_type(test_file.name, str(test_file))
    print(f"   Classified as: {doc_type}")
    
    # Should be classified as NDA
    assert doc_type == "nda", f"Expected 'nda', got '{doc_type}'"
    print("   ✅ Correctly classified as NDA")


def test_classify_real_agreement(mcp_servers):
    """Test classification of a real agreement document."""
    from python import server
    
    # Find an agreement PDF
    agreement_dir = Path(__file__).parent.parent / "data" / "Agreements"
    if not agreement_dir.exists():
        pytest.skip("Agreements directory not found")
    
    agreement_files = list(agreement_dir.glob("*.pdf"))
    if not agreement_files:
        pytest.skip("No agreement PDFs found")
    
    test_file = agreement_files[0]
    print(f"\n📄 Testing classification of: {test_file.name}")
    
    # Set MCP URLs
    import os
    os.environ["MCP_OCR_URL"] = mcp_servers["ocr_url"]
    os.environ["MCP_RAG_URL"] = mcp_servers["rag_url"]
    
    # Classify the document
    doc_type = server.classify_doc_type(test_file.name, str(test_file))
    print(f"   Classified as: {doc_type}")
    
    # Should be classified as some type of agreement (not default)
    assert doc_type != "default", f"Should not be 'default', got '{doc_type}'"
    print(f"   ✅ Correctly classified as {doc_type}")


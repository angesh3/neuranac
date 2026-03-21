"""Tests for RAGTroubleshooter — keyword retrieval and fallback analysis."""
import pytest
from app.rag_troubleshooter import RAGTroubleshooter, KNOWLEDGE_BASE


@pytest.fixture
def rag():
    return RAGTroubleshooter()


class TestKnowledgeBase:
    def test_kb_has_entries(self):
        assert len(KNOWLEDGE_BASE) == 12

    def test_kb_entries_have_required_fields(self):
        for doc in KNOWLEDGE_BASE:
            assert "id" in doc
            assert "title" in doc
            assert "content" in doc


class TestRetrieval:
    @pytest.mark.asyncio
    async def test_retrieve_eap_tls(self, rag):
        docs = await rag._retrieve("EAP-TLS authentication failure")
        assert len(docs) > 0
        assert any("EAP-TLS" in d["title"] for d in docs)

    @pytest.mark.asyncio
    async def test_retrieve_vlan(self, rag):
        docs = await rag._retrieve("VLAN assignment not working")
        assert len(docs) > 0
        assert any("VLAN" in d["title"] for d in docs)

    @pytest.mark.asyncio
    async def test_retrieve_shadow_ai(self, rag):
        docs = await rag._retrieve("shadow AI usage detected unauthorized")
        assert len(docs) > 0

    @pytest.mark.asyncio
    async def test_retrieve_returns_max_top_k(self, rag):
        docs = await rag._retrieve("authentication failure certificate", top_k=2)
        assert len(docs) <= 2

    @pytest.mark.asyncio
    async def test_retrieve_no_match(self, rag):
        docs = await rag._retrieve("xyzzy gibberish")
        assert len(docs) == 0


class TestKeywordAnalyze:
    def test_keyword_analyze_with_docs(self, rag):
        docs = [KNOWLEDGE_BASE[0]]  # EAP-TLS
        result = rag._keyword_analyze("EAP-TLS failure", docs, None)
        assert result["root_cause"] == "EAP-TLS Authentication Failure"
        assert result["source"] == "keyword_match"
        assert result["confidence"] == 0.6
        assert len(result["recommended_fixes"]) > 0

    def test_keyword_analyze_no_docs(self, rag):
        result = rag._keyword_analyze("unknown issue", [], None)
        assert result["source"] == "keyword_fallback"
        assert result["confidence"] == 0.2
        assert result["kb_docs_retrieved"] == 0


class TestTroubleshoot:
    @pytest.mark.asyncio
    async def test_troubleshoot_returns_result(self, rag):
        result = await rag.troubleshoot("MAB authentication failure MAC address")
        assert "root_cause" in result
        assert "recommended_fixes" in result
        assert "source" in result

    @pytest.mark.asyncio
    async def test_troubleshoot_coa_issue(self, rag):
        result = await rag.troubleshoot("CoA failure port 3799 blocked")
        assert "root_cause" in result
        assert result["kb_docs_retrieved"] > 0

import pytest
from app.engine.utils import infer_work_key, work_has_pdf_candidate, generate_work_key

class TestWorkKeyUtils:
    def test_infer_work_key_direct(self):
        key = "task:123:work:456"
        assert infer_work_key(key) == key

    def test_infer_work_key_download(self):
        work_key = "task:123:work:456"
        key = f"data:download:{work_key}"
        assert infer_work_key(key) == work_key

    def test_infer_work_key_parsed(self):
        work_key = "task:123:work:456"
        key = f"data:parsed:{work_key}"
        assert infer_work_key(key) == work_key

    def test_infer_work_key_index(self):
        work_key = "task:123:work:456"
        key = f"index:vector:{work_key}"
        assert infer_work_key(key) == work_key

    def test_infer_work_key_invalid(self):
        with pytest.raises(ValueError):
            infer_work_key("invalid:key:format")

    def test_infer_work_key_empty(self):
        with pytest.raises(ValueError):
            infer_work_key("")

    def test_generate_work_key(self):
        assert generate_work_key("abc", 1) == "task:abc:work:1"

class TestPdfCandidateFiltering:
    def test_has_pdf_in_best_oa(self):
        item = {
            "best_oa_location": {
                "pdf_url": "http://example.com/paper.pdf",
                "landing_page_url": "http://example.com/paper"
            }
        }
        assert work_has_pdf_candidate(item) is True

    def test_has_pdf_in_locations(self):
        item = {
            "best_oa_location": None,
            "locations": [
                {"pdf_url": None},
                {"pdf_url": "http://example.com/paper.pdf"}
            ]
        }
        assert work_has_pdf_candidate(item) is True

    def test_has_arxiv_landing_page(self):
        item = {
            "best_oa_location": {
                "pdf_url": None,
                "landing_page_url": "https://arxiv.org/abs/1234.5678"
            }
        }
        assert work_has_pdf_candidate(item) is True

    def test_no_pdf_candidate(self):
        item = {
            "best_oa_location": {
                "pdf_url": None,
                "landing_page_url": "http://example.com/paper"
            },
            "locations": []
        }
        assert work_has_pdf_candidate(item) is False

    def test_empty_item(self):
        assert work_has_pdf_candidate({}) is False

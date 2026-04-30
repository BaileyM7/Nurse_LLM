import json
from pathlib import Path

import pytest

from app.models.scenario import PatientScenario


@pytest.fixture
def sample_scenario() -> PatientScenario:
    p = Path(__file__).parent.parent / "data" / "scenarios" / "case_001.json"
    with open(p, encoding="utf-8") as f:
        return PatientScenario(**json.load(f))


@pytest.fixture
def fake_llm_response():
    """Returns a callable that builds a stub mimicking LangChain ChatModel.invoke."""
    def _make(content: str):
        class _Msg:
            def __init__(self, c):
                self.content = c

        class _Stub:
            def invoke(self, *_a, **_k):
                return _Msg(content)

            async def ainvoke(self, *_a, **_k):
                return _Msg(content)

            def bind(self, **_k):
                return self

        return _Stub()

    return _make

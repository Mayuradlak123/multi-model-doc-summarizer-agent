from typing import List, Dict, Any, TypedDict

class AgentState(TypedDict):
    filename: str
    chunks: List[Dict[str, Any]]
    raw_highlights: List[str]
    synthesized_markdown: str
    executive_summary: Any
    tone: str
    category: str
    entities: List[str]
    is_mock: bool
    steps_timeline: List[Dict[str, Any]]
    error: str

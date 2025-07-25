# backend/linkedin/graph_state.py
from typing import TypedDict, List, Dict, Any, Optional

class GraphState(TypedDict, total=False):
    post_id: Optional[int]             # Database post ID
    post_urn: Optional[str]            # Unique identifier for the LinkedIn post
    post_content: Optional[str]        # The text of the LinkedIn post
    is_relevant: Optional[str]         # 'PROCEED' or 'DISCARD'
    search_queries: Optional[List[str]]# List of generated search queries
    documents: Optional[List[dict]]    # List of curated, full-text documents
    research_summary: Optional[str]    # Synthesized briefing note from research
    final_comment: Optional[str]       # The drafted comment
    comment_quality_is_sufficient: Optional[str] # 'APPROVE' or 'REJECT'
    error: Optional[str]               # Error message if any
    # NEW ROUTING FIELDS
    content_type: Optional[str]        # "AI Technical Content", "PM Strategy Posts", etc.
    selected_strategy: Optional[str]   # "Lead with Analysis", "Lead with Experience", etc.
    target_word_count: Optional[int]   # Dynamic word count based on content type
    response_tone: Optional[str]       # "Evidence-based, analytical", etc.
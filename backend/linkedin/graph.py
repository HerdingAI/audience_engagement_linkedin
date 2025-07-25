# backend/linkedin/graph.py
import os
import logging
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .graph_state import GraphState
from .nodes import LinkedInNodes
from .services.sqlite_service import LinkedInSQLiteService

logger = logging.getLogger(__name__)

class LinkedInGraph:
    def __init__(self, db_path: str = "linkedin_project_db.sqlite3"):
        # Validate database path
        if not os.path.exists(db_path):
            logger.warning(f"Database file {db_path} does not exist, will be created")
        
        # Initialize services
        self.db_service = LinkedInSQLiteService(db_path)
        
        # Get API keys from environment
        openai_key = os.getenv("OPENAI_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")
        tavily_key = os.getenv("TAVILY_API_KEY")
        
        if not all([openai_key, gemini_key, tavily_key]):
            missing = [k for k, v in [("OPENAI_API_KEY", openai_key), ("GEMINI_API_KEY", gemini_key), ("TAVILY_API_KEY", tavily_key)] if not v]
            raise ValueError(f"Missing required API keys: {missing}")
        
        # Initialize nodes
        self.nodes = LinkedInNodes(
            openai_key=openai_key,
            gemini_key=gemini_key, 
            tavily_key=tavily_key,
            db_service=self.db_service
        )
        
        # Build the graph
        self.app = self._build_graph()
    
    def _build_graph(self):
        """Build the LangGraph workflow"""
        
        # Create standalone node functions (LangGraph compatibility)
        def post_retriever(state):
            return self.nodes.post_retriever_node(state)
        
        def post_gatekeeper(state):
            return self.nodes.post_gatekeeper_node(state)
        
        def post_researcher(state):
            return self.nodes.post_researcher_node(state)
        
        def research_engine(state):
            return self.nodes.research_engine_node(state)
        
        def research_synthesis(state):
            return self.nodes.research_synthesis_node(state)
        
        def comment_crafter_legacy(state):
            return self.nodes.comment_crafter_node_legacy(state)
        
        def final_quality_check(state):
            return self.nodes.final_quality_check_node(state)
        
        def comment_saver(state):
            return self.nodes.comment_saver_node(state)
        
        # Create the state graph
        workflow = StateGraph(GraphState)
        
        # Add nodes using standalone functions
        workflow.add_node("post_retriever", post_retriever)
        workflow.add_node("post_gatekeeper", post_gatekeeper)
        workflow.add_node("post_researcher", post_researcher)
        workflow.add_node("research_engine", research_engine)
        workflow.add_node("research_synthesis", research_synthesis)
        # New routing and specialized crafters
        workflow.add_node("decision_router", lambda state: self.nodes.decision_router_node(state))
        workflow.add_node("analytical_expert_crafter", lambda state: self.nodes.analytical_expert_crafter_node(state))
        workflow.add_node("strategic_implementer_crafter", lambda state: self.nodes.strategic_implementer_crafter_node(state))
        workflow.add_node("curious_professional_crafter", lambda state: self.nodes.curious_professional_crafter_node(state))
        workflow.add_node("comment_crafter_legacy", comment_crafter_legacy)
        # Quality check and saver
        workflow.add_node("final_quality_check", final_quality_check)
        workflow.add_node("comment_saver", comment_saver)
        
        # Add conditional edges (routers)
        workflow.add_conditional_edges(
            "post_gatekeeper",
            self._route_after_gatekeeper,
            {"proceed": "post_researcher", "discard": END}
        )
        # Content-aware routing after research synthesis
        workflow.add_conditional_edges(
            "decision_router",
            self._route_to_appropriate_crafter,
            {
                "analytical_expert": "analytical_expert_crafter",
                "strategic_implementer": "strategic_implementer_crafter",
                "curious_professional": "curious_professional_crafter",
                "fallback": "comment_crafter_legacy"
            }
        )
        # Final quality check routing
        workflow.add_conditional_edges(
            "final_quality_check",
            self._route_after_quality_check,
            {"approve": "comment_saver", "reject": END}
        )
        
        # Add regular edges
        workflow.add_edge("post_retriever", "post_gatekeeper")
        workflow.add_edge("post_researcher", "research_engine")
        workflow.add_edge("research_engine", "research_synthesis")
        workflow.add_edge("research_synthesis", "decision_router")
        # Connect all crafters to quality check
        workflow.add_edge("analytical_expert_crafter", "final_quality_check")
        workflow.add_edge("strategic_implementer_crafter", "final_quality_check")
        workflow.add_edge("curious_professional_crafter", "final_quality_check")
        workflow.add_edge("comment_crafter_legacy", "final_quality_check")
        workflow.add_edge("comment_saver", END)
        
        # Set entry point
        workflow.set_entry_point("post_retriever")
        
        # Compile the graph
        return workflow.compile()

    def _route_to_appropriate_crafter(self, state: GraphState) -> str:
        """Router: Direct to appropriate crafter based on content analysis"""
        selected = state.get("selected_strategy", "")
        mapping = {
            "Lead with Analysis": "analytical_expert",
            "Lead with Experience": "strategic_implementer",
            "Lead with Questions": "curious_professional",
            "Lead with Comparative Insight": "curious_professional",
            "Lead with Personal Example": "strategic_implementer"
        }
        route = mapping.get(selected, "curious_professional")
        logger.info(f"Routing to: {route} (strategy: {selected})")
        return route
    
    def _route_after_gatekeeper(self, state: GraphState) -> str:
        """Router 1: Route based on gatekeeper decision"""
        is_relevant = state.get("is_relevant", "DISCARD")
        
        if is_relevant == "PROCEED":
            logger.info("Post approved by gatekeeper, proceeding to research")
            return "proceed"
        else:
            logger.info("Post discarded by gatekeeper")
            # Mark as discarded in database if we have the required fields
            try:
                if state.get("post_id") and state.get("post_urn"):
                    self.db_service.mark_post_discarded(
                        state["post_id"], 
                        state["post_urn"],
                        "DISCARDED_BY_GATEKEEPER"
                    )
            except Exception as e:
                logger.error(f"Error marking post as discarded: {e}")
            return "discard"
    
    def _route_after_quality_check(self, state: GraphState) -> str:
        """Router 2: Route based on quality check decision"""
        quality_sufficient = state.get("comment_quality_is_sufficient", "REJECT")
        
        if quality_sufficient == "APPROVE":
            logger.info("Comment approved by quality check, saving to database")
            return "approve"
        else:
            logger.info("Comment rejected by quality check")
            # Mark as rejected in database if we have the required fields
            try:
                if state.get("post_id") and state.get("post_urn"):
                    self.db_service.mark_comment_rejected(
                        state["post_id"],
                        state["post_urn"], 
                        state.get("final_comment", ""),
                        "REJECTED_BY_QC"
                    )
            except Exception as e:
                logger.error(f"Error marking comment as rejected: {e}")
            return "reject"
    
    def run(self, thread_id: str = "default") -> Dict[str, Any]:
        """Run the graph to process one post (synchronous)"""
        try:
            logger.info("Starting LinkedIn comment generation process")
            
            # Check if there are posts to process
            unprocessed_post = self.db_service.get_unprocessed_post()
            if not unprocessed_post:
                logger.info("No unprocessed posts found")
                return {"status": "no_posts", "message": "No unprocessed posts found"}
            
            # Initialize state with required default values
            initial_state = {
                "post_id": 0,
                "post_urn": "",
                "post_content": "",
                "is_relevant": "",
                "search_queries": [],
                "documents": [],
                "research_summary": "",
                "final_comment": "",
                "comment_quality_is_sufficient": "",
                "error": ""
            }
            
            # Run the graph synchronously
            config = {"configurable": {"thread_id": thread_id}}
            final_state = self.app.invoke(initial_state, config)
            
            logger.info("LinkedIn comment generation process completed")
            return final_state
            
        except Exception as e:
            logger.error(f"Error running LinkedIn graph: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_stats(self) -> dict:
        """Get processing statistics"""
        return self.db_service.get_processing_stats()
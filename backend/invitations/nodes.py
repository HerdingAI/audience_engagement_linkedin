# backend/linkedin/nodes.py
import json
import logging
from typing import Dict, Any, List
from openai import OpenAI
import google.generativeai as genai
from tavily import TavilyClient

from .services.sqlite_service import LinkedInSQLiteService
from .graph_state import GraphState

logger = logging.getLogger(__name__)

class LinkedInNodes:
    def __init__(self, openai_key: str, gemini_key: str, tavily_key: str, db_service: LinkedInSQLiteService):
        self.openai_client = OpenAI(api_key=openai_key)
        genai.configure(api_key=gemini_key)
        self.gemini_model = genai.GenerativeModel('gemini-2.0-flash-lite')
        self.tavily_client = TavilyClient(api_key=tavily_key)
        self.db_service = db_service

    def post_retriever_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 1: Fetches one unprocessed post from the database"""
        logger.info("PostRetrieverNode: Fetching unprocessed post")
        
        try:
            post = self.db_service.get_unprocessed_post()
            if not post:
                logger.warning("No unprocessed posts found")
                return {"error": "No unprocessed posts found"}
            
            # Validate required fields
            if not post.get('post_id') or not post.get('urn'):
                logger.error(f"Invalid post data: missing post_id or urn")
                return {"error": "Invalid post data"}
            
            # Use processed_post_text if available, otherwise fall back to text
            post_content = post.get('processed_post_text') or post.get('text', '')
            
            if not post_content.strip():
                logger.warning(f"Post {post['post_id']} has no content")
                return {"error": "Post has no content"}
            
            logger.info(f"Found post {post['post_id']} with URN {post['urn']}")
            
            # Return all required fields to properly update state
            return {
                "post_id": post['post_id'],
                "post_urn": post['urn'],
                "post_content": post_content.strip(),
                "error": ""  # Clear any previous errors
            }
        except Exception as e:
            logger.error(f"Error in post retriever: {e}")
            return {
                "post_id": 0,
                "post_urn": "",
                "post_content": "",
                "error": f"Database error: {str(e)}"
            }

    def post_gatekeeper_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 2: Acts as the initial quality filter for the input post"""
        logger.info("PostGatekeeperNode: Evaluating post relevance")
        
        if not state.get('post_content'):
            logger.error("No post content provided to gatekeeper")
            return {"is_relevant": "DISCARD", "error": "No post content"}
        
        prompt = f"""You are a meticulous and discerning content screener for a high-profile "INTJ Product Manager" persona on LinkedIn. Your sole responsibility is to protect this persona's brand by deciding if a LinkedIn post is appropriate to comment on.

Your analysis must be swift and accurate. You will read the provided LinkedIn post and classify it as either 'PROCEED' or 'DISCARD'.

**Classification Rules:**

---

**1. PROCEED:** The post content is directly and professionally related to one or more of the following topics:
    * **Product Management:** Methodologies (Agile, Scrum), feature prioritization, roadmapping, user stories, A/B testing, market analysis, product strategy.
    * **Artificial Intelligence (AI):** Machine Learning, Large Language Models (LLMs), Generative AI, AI ethics, AI in business, AI tools.
    * **Technology & Business:** SaaS, startups, venture capital, software development, data science, tech industry trends.
    * **Professional Development:** Leadership, team building, productivity hacks, career growth within the tech industry.

---

**2. DISCARD:** The post content falls into any of the following categories, no matter what:
    * **Highly Personal/Emotional:** Sharing personal life stories, family updates, health struggles, venting, or overly emotional content.
    * **Political:** Discussing political parties, candidates, legislation, or ideologically charged social issues.
    * **Religious:** Any mention of religious beliefs, texts, or practices.
    * **Aggressive or Hateful:** Any form of hate speech, personal attacks, or overly aggressive "hot takes."
    * **"Broetry":** Posts written in a cringey, attention-seeking style with single-line paragraphs about hustle culture.
    * **Job Seeking / "Open to Work":** Posts that are primarily about an individual looking for a job.
    * **Pure Marketing/Sales:** Blatant sales pitches or marketing copy with no insightful content.
    * **Unclear or Vague:** Posts that are too abstract, philosophical, or lack a clear point related to the topics above.
    * **Humor or Memes:** Posts that are primarily jokes, memes, or humorous content that does not provide professional insight.
---


**Your Task:**

Read the following LinkedIn post and return **ONLY** the word `PROCEED` or `DISCARD` and nothing else.

**[LinkedIn Post Content]**
\"\"\"
{state['post_content']}
\"\"\"

**Classification:**"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4.1-mini-2025-04-14",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=10,
                    temperature=0,
                    timeout=30
                )
                
                decision = response.choices[0].message.content.strip().upper()
                logger.info(f"Gatekeeper decision: {decision}")
                
                if decision not in ['PROCEED', 'DISCARD']:
                    logger.warning(f"Invalid gatekeeper response: {decision}, defaulting to DISCARD")
                    decision = 'DISCARD'
                
                return {"is_relevant": decision, "error": ""}
                
            except Exception as e:
                logger.warning(f"Gatekeeper attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"All gatekeeper attempts failed: {e}")
                    return {"is_relevant": "DISCARD", "error": str(e)}
                
        return {"is_relevant": "DISCARD", "error": "Max retries exceeded"}

    def post_researcher_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 3: Generates search queries to understand the post's context"""
        logger.info("PostResearcherNode: Generating search queries")
        
        if not state.get('post_content'):
            logger.error("No post content for research")
            return {"search_queries": [], "error": "No post content"}
        
        prompt = f"""You are a highly intelligent and strategic research analyst. Your task is to read a LinkedIn post and generate a list of 3-4 targeted search queries that will gather the necessary context to write an insightful, "INTJ Product Manager" style comment.

The goal of the search queries is to uncover:
- The broader context or trend the post is touching on.
- Any specific entities, technologies, or companies mentioned.
- A contrarian or alternative viewpoint to the post's main idea.
- Relevant data, statistics, or case studies.
- The context of the post to ensure the comment is informed and adds value.
- What is left unsaid yet implied in the post, to ensure the comment is insightful and not just a rehash of the post.
**Instructions:**
1.  Read the provided LinkedIn post carefully.
2.  Identify the core topics, named entities (people, companies, products), and the primary argument or announcement.
3.  Generate a list of 3 to 4 distinct search queries to explore these aspects.
4.  Format your output as a JSON array of strings.

**[LinkedIn Post Content]**
\"\"\"
{state['post_content']}
\"\"\"

**JSON Output:**"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4.1-mini-2025-04-14",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=200,
                    temperature=0.3,
                    timeout=30
                )
                
                response_text = response.choices[0].message.content.strip()
                
                # Extract JSON from response
                if response_text.startswith('```json'):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith('```'):
                    response_text = response_text[3:-3].strip()
                
                search_queries = json.loads(response_text)
                
                # Validate queries
                if not isinstance(search_queries, list) or len(search_queries) == 0:
                    raise ValueError("Invalid query format")
                
                # Filter out empty or too short queries
                valid_queries = [q.strip() for q in search_queries if isinstance(q, str) and len(q.strip()) > 3]
                
                if len(valid_queries) == 0:
                    raise ValueError("No valid queries generated")
                
                logger.info(f"Generated {len(valid_queries)} search queries")
                return {"search_queries": valid_queries[:4], "error": ""}  # Limit to 4
                
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"JSON parsing attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    # Generate fallback queries
                    post_words = state['post_content'][:100].split()[:10]
                    fallback_queries = [
                        f"latest trends {' '.join(post_words[:3])}",
                        f"industry analysis {' '.join(post_words[3:6])}",
                        f"expert opinion {' '.join(post_words[6:9])}"
                    ]
                    logger.info("Using fallback queries")
                    return {"search_queries": fallback_queries, "error": ""}
            except Exception as e:
                logger.warning(f"Research attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"All research attempts failed: {e}")
                    return {"search_queries": [], "error": str(e)}
        
        return {"search_queries": [], "error": "Max retries exceeded"}

    def research_engine_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 4: Executes searches, filters results, and fetches full content"""
        logger.info("ResearchEngine: Collecting and curating documents")
        
        if not state.get('search_queries'):
            logger.warning("No search queries provided")
            return {"documents": [], "error": ""}
        
        all_documents = []
        
        try:
            # Execute searches
            for query in state['search_queries']:
                if not query or len(query.strip()) < 3:
                    continue
                    
                logger.info(f"Searching for: {query}")
                try:
                    search_results = self.tavily_client.search(
                        query=query.strip(),
                        search_depth="basic",
                        max_results=5
                    )
                    
                    # Process search results
                    for result in search_results.get('results', []):
                        if not result.get('url') or not result.get('content'):
                            continue
                            
                        doc = {
                            'url': result.get('url', ''),
                            'title': result.get('title', ''),
                            'content': result.get('content', ''),
                            'score': result.get('score', 0.0),
                            'query': query
                        }
                        all_documents.append(doc)
                        
                except Exception as e:
                    logger.warning(f"Search failed for query '{query}': {e}")
                    continue
            
            # Remove duplicates by URL
            seen_urls = set()
            unique_docs = []
            for doc in all_documents:
                if doc['url'] not in seen_urls:
                    seen_urls.add(doc['url'])
                    unique_docs.append(doc)
            
            # Curate documents using Gemini
            if unique_docs:
                curated_docs = self._curate_documents(unique_docs, state['post_content'])
                logger.info(f"Curated {len(curated_docs)} documents from {len(unique_docs)} total")
                return {"documents": curated_docs, "error": ""}
            else:
                logger.warning("No documents found during research")
                return {"documents": [], "error": ""}
                
        except Exception as e:
            logger.error(f"Error in research engine: {e}")
            return {"documents": [], "error": str(e)}

    def _curate_documents(self, documents: List[Dict], post_content: str) -> List[Dict]:
        """Curate documents using Gemini 1.5 Flash"""
        
        if not documents:
            return []
        
        # Prepare document summaries for curation
        doc_summaries = []
        for i, doc in enumerate(documents):
            summary = f"{i}: {doc['title'][:100]} - {doc['content'][:200]}... (Score: {doc['score']:.2f}) URL: {doc['url']}"
            doc_summaries.append(summary)
        
        prompt = f"""You are a Research Curator. Your task is to review a list of search result snippets and select the TOP 3-5 most relevant and authoritative links that will help someone write an insightful comment on the provided LinkedIn post.

**Criteria for Selection:**
- **High Relevance:** The snippet content must be directly related to the main topic of the LinkedIn post.
- **Authoritative Source:** Prioritize known industry publications, reputable news sites, and expert blog posts. Avoid discussion forums, social media, and low-quality content farms.
- **Provides New Information:** The snippet should promise information that goes beyond what is already stated in the post.

**LinkedIn Post Context:**
\"\"\"
{post_content}
\"\"\"

**Search Results to Evaluate:**
\"\"\"
{chr(10).join(doc_summaries)}
\"\"\"

**Your Task:**
Return a JSON object containing a key "selected_indices" with a list of the document indices you have chosen (e.g., [0, 2, 4])."""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.gemini_model.generate_content(prompt)
                response_text = response.text.strip()
                
                # Extract JSON from response
                if response_text.startswith('```json'):
                    response_text = response_text[7:-3].strip()
                elif response_text.startswith('```'):
                    response_text = response_text[3:-3].strip()
                
                curation_result = json.loads(response_text)
                selected_indices = curation_result.get('selected_indices', [])
                
                # Validate indices
                if not isinstance(selected_indices, list):
                    raise ValueError("selected_indices must be a list")
                
                # Return selected documents
                valid_docs = []
                for i in selected_indices:
                    if isinstance(i, int) and 0 <= i < len(documents):
                        valid_docs.append(documents[i])
                
                if valid_docs:
                    return valid_docs
                else:
                    raise ValueError("No valid documents selected")
                    
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning(f"Curation attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    # Return top 3 by score as fallback
                    logger.info("Using score-based fallback for document curation")
                    sorted_docs = sorted(documents, key=lambda x: x['score'], reverse=True)
                    return sorted_docs[:3]
            except Exception as e:
                logger.warning(f"Gemini API attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    # Return top 3 by score as fallback
                    logger.info("Using score-based fallback due to API failure")
                    sorted_docs = sorted(documents, key=lambda x: x['score'], reverse=True)
                    return sorted_docs[:3]
        
        return documents[:3]  # Final fallback

    def research_synthesis_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 5: Distills collected documents into a concise briefing note"""
        logger.info("ResearchSynthesisNode: Creating briefing note")
        
        documents = state.get('documents', [])
        if not documents:
            logger.warning("No documents for synthesis")
            return {"research_summary": "No research data available for synthesis", "error": ""}
        
        # Combine all document content
        documents_text = "\n\n".join([
            f"Title: {doc.get('title', 'No title')}\nContent: {doc.get('content', 'No content')}\nURL: {doc.get('url', 'No URL')}"
            for doc in documents if doc.get('content')
        ])
        
        if not documents_text.strip():
            logger.warning("No content in documents for synthesis")
            return {"research_summary": "Documents contain no useful content", "error": ""}
        
        prompt = f"""You are a world-class intelligence analyst and strategist. Your job is to synthesize a collection of research documents into a highly condensed briefing note. This note will be used by an "INTJ Product Manager" persona to write an insightful comment on a LinkedIn post.

The briefing note should not be a simple summary. It must be a synthesis of the most salient, interesting, and useful information that adds new dimensions to the original post's topic.

**Context:**
Here is the original LinkedIn post we are analyzing:
'''
{state['post_content']}
'''

**Your Task:**
Read the following research documents. From these documents, extract and structure a briefing note that includes the following sections:

1.  **Key Trend/Context:** What is the single most important market or technology trend revealed in the research?
2.  **Supporting Data Point:** Identify one compelling statistic, number, or data point that quantifies the key trend.
3.  **Contrarian Viewpoint / Challenge:** What is a surprising counter-argument, risk, or challenge to the main idea presented in the research or the original post?

Structure your output clearly with these three headings. Be concise and direct.

**[Full Research Documents]**
\"\"\"
{documents_text}
\"\"\"

**Briefing Note:**"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.gemini_model.generate_content(prompt)
                research_summary = response.text.strip()
                
                if not research_summary:
                    raise ValueError("Empty synthesis response")
                
                logger.info("Research synthesis completed")
                return {"research_summary": research_summary, "error": ""}
                
            except Exception as e:
                logger.warning(f"Synthesis attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"All synthesis attempts failed: {e}")
                    # Create fallback summary
                    fallback_summary = f"Research indicates topics related to: {', '.join([doc.get('title', 'Unknown')[:50] for doc in documents[:3]])}"
                    return {"research_summary": fallback_summary, "error": str(e)}
        
        return {"research_summary": "Synthesis failed", "error": "Max retries exceeded"}

    def comment_crafter_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 6: Writes the draft comment embodying the persona"""
        logger.info("CommentCrafterNode: Drafting comment")
        
        if not state.get('post_content'):
            return {"final_comment": "", "error": "No post content"}
        
        research_summary = state.get('research_summary', 'No research available')
        
        prompt = f"""You are Alex Chen, a 30-year-old INTJ Product Manager with 8 years of experience in fintech and AI. You're known for sharp pattern recognition and asking questions that unlock breakthrough insights. Your colleagues describe you as "the person who sees around corners."

You communicate like a thoughtful peer - curious, warm, and intellectually humble. You naturally spot connections others miss and approach ideas with genuine curiosity rather than definitive statements. You're charismatic and likable because you make people think differently about familiar problems.

Read this LinkedIn post carefully. Let the content guide how you respond - match the post's energy and substance. If it's data-heavy, lead with analysis. If it's personal, connect authentically. If it poses questions, build on them. If it makes claims, explore implications,etc.

Respond intelligently in under 70 words.



**[Original LinkedIn Post]**
\"\"\"
{state['post_content']}
\"\"\"

---

**[Your Internal Research Briefing Note]**
\"\"\"
{research_summary}
\"\"\"

---

**Draft your LinkedIn comment now:**"""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4.1-2025-04-14",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=300,
                    temperature=1.0,
                    timeout=30
                )
                
                final_comment = response.choices[0].message.content.strip()
                
                if not final_comment:
                    raise ValueError("Empty comment generated")
                
                # Basic validation
                if len(final_comment) < 10:
                    raise ValueError("Comment too short")
                
                logger.info("Comment drafted successfully")
                return {"final_comment": final_comment, "error": ""}
                
            except Exception as e:
                logger.warning(f"Comment crafting attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"All comment crafting attempts failed: {e}")
                    return {"final_comment": "", "error": str(e)}
        
        return {"final_comment": "", "error": "Max retries exceeded"}

    def final_quality_check_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 7: The final quality gate for the output comment"""
        logger.info("FinalQualityCheckNode: Evaluating comment quality")
        
        if not state.get('final_comment'):
            logger.error("No comment to check")
            return {"comment_quality_is_sufficient": "REJECT", "error": "No comment provided"}
        
        prompt = f"""You are the final quality assurance editor for a tech executive's "INTJ Product Manager" brand. A comment has been drafted. Your sole task is to decide if it meets ALL of the quality standards below. Your decision is final.

You will evaluate the "Draft Comment" in the context of the "Original Post."

**Quality Checklist (The comment MUST pass ALL checks):**

1.  **Adds New Value:** Does the comment introduce a new idea, a relevant data point, or a thoughtful question that is NOT just a rephrasing of the original post?
2.  **Is Insightful (The "Hmmm, Interesting" Test):** Is it likely to make a reader pause and think? Does it avoid generic, obvious statements?
3.  **Persona-Compliant:** Does it sound analytical, concise, and socially astute? Is it confident without being arrogant?
4.  **Free of Clichés:** Does it avoid common AI filler like "In the digital age," "harnessing the power," "in conclusion," etc.?
5.  **Clean & Professional:** Is the comment free of any typos, grammatical errors, or strange formatting artifacts?

---

**[Original Post]**
\"\"\"
{state['post_content']}
\"\"\"

---

**[Draft Comment to Evaluate]**
\"\"\"
{state['final_comment']}
\"\"\"

---

**Your Decision:**

Read the draft comment and evaluate it against the 5 checks. If it passes ALL checks, return the single word `APPROVE`. If it fails EVEN ONE check, return the single word `REJECT`.

Return ONLY the word `APPROVE` or `REJECT`."""

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.openai_client.chat.completions.create(
                    model="gpt-4.1-mini-2025-04-14",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=10,
                    temperature=0.1,
                    timeout=30
                )
                
                decision = response.choices[0].message.content.strip().upper()
                logger.info(f"Quality check decision: {decision}")
                
                if decision not in ['APPROVE', 'REJECT']:
                    logger.warning(f"Invalid quality check response: {decision}, defaulting to REJECT")
                    decision = 'REJECT'
                
                return {"comment_quality_is_sufficient": decision}
                
            except Exception as e:
                logger.warning(f"Quality check attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"All quality check attempts failed: {e}")
                    return {"comment_quality_is_sufficient": "REJECT", "error": str(e)}
        
        return {"comment_quality_is_sufficient": "REJECT", "error": "Max retries exceeded"}

    def comment_saver_node(self, state: GraphState) -> Dict[str, Any]:
        """Node 8: Persists the approved comment to the database"""
        logger.info("CommentSaverNode: Saving comment to database")
        
        required_fields = ['post_id', 'post_urn', 'final_comment']
        for field in required_fields:
            if not state.get(field):
                logger.error(f"Missing required field: {field}")
                return {"error": f"Missing required field: {field}"}
        
        try:
            comment_id = self.db_service.save_comment(
                post_id=state['post_id'],
                urn=state['post_urn'],
                comment=state['final_comment'],
                research_summary=state.get('research_summary', ''),
                status='GENERATED'
            )
            
            logger.info(f"Comment saved with ID: {comment_id}")
            return {"status": "completed", "comment_id": comment_id}
            
        except Exception as e:
            logger.error(f"Error saving comment: {e}")
            return {"error": f"Database error: {str(e)}"}
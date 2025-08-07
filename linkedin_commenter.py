# linkedin_commenter.py
import logging
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Add the project root to the Python path
project_root = Path(__file__).parent.absolute()
sys.path.insert(0, str(project_root))

try:
    from backend.linkedin.graph import LinkedInGraph
except ImportError as e:
    print(f"Import error: {e}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Project root: {project_root}")
    print(f"Python path: {sys.path}")
    sys.exit(1)

# Load environment variables
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=True)
else:
    # Try loading from current directory
    if Path('.env').exists():
        load_dotenv(override=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('linkedin_commenter.log')
    ]
)

logger = logging.getLogger(__name__)

def validate_environment() -> bool:
    """Validate required environment variables and database"""
    required_vars = ["OPENAI_API_KEY", "GEMINI_API_KEY", "TAVILY_API_KEY"]
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set these in your .env file or environment")
        return False
    
    # Check if database file exists
    db_path = "linkedin_project_db.sqlite3"
    if not Path(db_path).exists():
        logger.error(f"Database file {db_path} not found")
        logger.error("Please ensure the LinkedIn database exists with posts table")
        return False
    
    return True

def main():
    """Main function to process one LinkedIn post"""
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="LinkedIn Comment Generator and Poster")
    parser.add_argument(
        "--max-posts", 
        type=int, 
        default=10, 
        help="Maximum number of posts to process (default: 10)"
    )
    parser.add_argument(
        "--db-path",
        type=str,
        default="linkedin_project_db.sqlite3",
        help="Path to the SQLite database file"
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Set the logging level"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (don't actually post comments)"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    try:
        logger.info("=== LinkedIn Commenter Starting ===")
        
        # Validate environment
        if not validate_environment():
            return False
        
        # Initialize the graph
        logger.info("Initializing LinkedIn graph...")
        try:
            graph = LinkedInGraph()
        except Exception as e:
            logger.error(f"Failed to initialize graph: {e}")
            return False
        
        # Show current stats
        try:
            stats = graph.get_stats()
            logger.info(f"Database stats: {stats}")
            
            if stats['total_posts'] == 0:
                logger.warning("No posts found in database")
                return False
            
            unprocessed_count = stats['total_posts'] - stats['processed_posts']
            if unprocessed_count == 0:
                logger.info("All posts have been processed")
                return True
            
            logger.info(f"Found {unprocessed_count} unprocessed posts")
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return False
        
        # Process posts in a loop (one at a time through the graph)
        posts_processed = 0
        max_posts = args.max_posts  # Use command line argument
        
        if args.dry_run:
            logger.info("Running in DRY-RUN mode - no comments will be posted")
        
        while posts_processed < max_posts:
            logger.info(f"Processing post {posts_processed + 1}...")
            try:
                result = graph.run()
            except Exception as e:
                logger.error(f"Error during graph execution: {e}")
                break
            
            # Check results
            if result.get("status") == "no_posts":
                logger.info("No more unprocessed posts found")
                break  # Exit the loop when no more posts
            elif result.get("error"):  # Check if error field has actual content
                logger.error(f"Processing failed: {result['error']}")
                # Continue to next post instead of exiting
                posts_processed += 1
                continue
            else:
                logger.info("Post processing completed successfully")
                posts_processed += 1
                
                # Show updated stats
                try:
                    updated_stats = graph.get_stats()
                    logger.info(f"Updated stats: {updated_stats}")
                except Exception as e:
                    logger.warning(f"Error getting updated stats: {e}")
        
        logger.info(f"=== LinkedIn Commenter Finished - Processed {posts_processed} posts ===")
        
        # Cleanup: Move profiles with no generated comments to next stage
        try:
            logger.info("Running cleanup for profiles without generated comments...")
            cleaned_up = graph.db_service.cleanup_profiles_without_comments()
            if cleaned_up > 0:
                logger.info(f"Cleanup completed: {cleaned_up} profiles moved to next stage")
            else:
                logger.info("No profiles required cleanup")
        except Exception as e:
            logger.warning(f"Error during profile cleanup: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
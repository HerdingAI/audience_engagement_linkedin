import os
import logging
import sqlite3
import requests
from datetime import datetime, timezone
from pipeline_manager import SimplifiedPipelineManager

class LinkedInScraper:
    def __init__(self, db_path, api_key):
        """
        Initializes the LinkedInScraper instance.
        :param db_path: Path to the SQLite database file.
        :param api_key: Your RapidAPI LinkedIn API key.
        """
        self.db_path = db_path
        self.api_key = api_key
        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "fresh-linkedin-profile-data.p.rapidapi.com"
        }
        self.logger = self.setup_logger()
        self._verify_and_update_database()
        self.logger.info("LinkedInScraper initialized successfully.")

    def setup_logger(self):
        """
        Sets up a logger that writes to both console and file.
        :return: A configured logging.Logger instance.
        """
        logs_directory = "logs"
        if not os.path.exists(logs_directory):
            os.makedirs(logs_directory)

        logger = logging.getLogger("LinkedInScraper")
        logger.setLevel(logging.DEBUG)

        # Console handler (INFO level)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        console_handler.setFormatter(console_format)

        # File handler (DEBUG level)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file_path = os.path.join(logs_directory, f"linkedin_scraper_{timestamp}.log")
        file_handler = logging.FileHandler(log_file_path)
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(file_format)

        # Avoid adding multiple handlers if logger already set
        if not logger.handlers:
            logger.addHandler(console_handler)
            logger.addHandler(file_handler)

        return logger

    def _verify_and_update_database(self):
        """
        Verifies that the required tables exist and adds missing columns.
        """
        conn = None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Check if required tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = set(t[0] for t in cursor.fetchall())
            required_tables = {"profiles", "posts", "media"}
            missing = required_tables - tables
            if missing:
                raise ValueError(f"Missing required tables in database: {missing}")

            # Add missing columns to posts table
            new_columns = [
                ("entertainments_count", "INTEGER DEFAULT 0"),
                ("poster_first_name", "TEXT"),
                ("poster_last_name", "TEXT"),
                ("poster_headline", "TEXT"),
                ("poster_image_url", "TEXT"),
                ("poster_linkedin_url", "TEXT"),
                ("poster_public_id", "TEXT"),
                ("article_title", "TEXT"),
                ("article_subtitle", "TEXT"),
                ("article_target_url", "TEXT"),
                ("article_description", "TEXT"),
                ("reshared", "BOOLEAN DEFAULT 0"),
                ("resharer_comment", "TEXT")
            ]

            for column_name, column_def in new_columns:
                try:
                    cursor.execute(f"ALTER TABLE posts ADD COLUMN {column_name} {column_def}")
                    self.logger.info(f"Added column {column_name} to posts table")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        self.logger.debug(f"Column {column_name} already exists")
                    else:
                        raise

            conn.commit()
            self.logger.info("Database verification and update successful.")
        except Exception as e:
            self.logger.error(f"Database verification failed: {str(e)}")
            raise
        finally:
            if conn:
                conn.close()

    def get_db_connection(self):
        """
        Gets a connection to the SQLite database.
        :return: A sqlite3.Connection object.
        """
        try:
            conn = sqlite3.connect(self.db_path)
            return conn
        except Exception as e:
            self.logger.error(f"Failed to connect to database: {str(e)}")
            raise

    def fetch_linkedin_posts(self, profile_url):
        """
        Fetches LinkedIn posts for a given profile URL using the new LinkedIn API.
        :param profile_url: The full LinkedIn profile URL.
        :return: A list of post objects returned by the API.
        """
        url = "https://fresh-linkedin-profile-data.p.rapidapi.com/get-profile-posts"
        
        query_params = {
            "linkedin_url": profile_url,
            "type": "posts"
        }

        self.logger.info(f"Fetching posts for profile: {profile_url}")
        
        try:
            response = requests.get(url, headers=self.headers, params=query_params)
            if response.status_code == 200:
                data = response.json()
                self.logger.debug(f"API response data: {data}")
                
                if data.get("message") == "ok":
                    posts = data.get("data", [])
                    self.logger.info(f"Successfully fetched {len(posts)} posts")
                    return posts
                else:
                    self.logger.warning(f"API response indicates failure: {data.get('message')}")
                    return []
            else:
                self.logger.error(
                    f"Error fetching posts for '{profile_url}': "
                    f"{response.status_code} - {response.text}"
                )
                return []
        except Exception as e:
            self.logger.error(f"Exception while fetching posts: {str(e)}")
            return []

    def _extract_media(self, post, post_id):
        """
        Extracts media from post and saves to media table.
        :param post: Post dictionary from API
        :param post_id: Database post_id for foreign key
        :return: List of media items extracted
        """
        media_items = []
        
        try:
            # Handle images
            if post.get('images'):
                for image in post['images']:
                    media_items.append({
                        'post_id': post_id,
                        'media_url': image.get('url'),
                        'media_type': 'image'
                    })
            
            # Handle video
            if post.get('video'):
                media_items.append({
                    'post_id': post_id,
                    'media_url': post['video'].get('stream_url'),
                    'media_type': 'video'
                })
            
            # Handle document
            if post.get('document'):
                media_items.append({
                    'post_id': post_id,
                    'media_url': post['document'].get('url'),
                    'media_type': 'document'
                })
                
        except Exception as e:
            self.logger.error(f"Error extracting media: {str(e)}")
        
        return media_items

    def _save_media(self, media_items, cursor):
        """
        Saves media items to the media table using an existing cursor.
        :param media_items: List of media dictionaries
        :param cursor: Existing database cursor to use
        """
        if not media_items:
            return

        insert_sql = """INSERT OR IGNORE INTO media (
            post_id, media_url, media_type
        ) VALUES (?, ?, ?);"""

        try:
            for media in media_items:
                cursor.execute(insert_sql, (
                    media['post_id'],
                    media['media_url'],
                    media['media_type']
                ))
            
            self.logger.info(f"Saved {len(media_items)} media items")
        except Exception as e:
            self.logger.error(f"Error saving media: {str(e)}")
            raise

    def save_posts(self, posts, profile_id):
        """
        Saves posts to the 'posts' table with new field mappings.
        :param posts: A list of post dictionaries from the LinkedIn API.
        :param profile_id: The local profile_id (FK) that maps to the 'profiles' table.
        """
        if not posts:
            self.logger.info("No posts to save.")
            return

        insert_sql = """INSERT OR IGNORE INTO posts (
            urn, profile_id, text, cleaned_text, category, media_type, 
            media_url, post_url, processed_post_text, total_reaction_count,
            like_count, appreciation_count, empathy_count, interest_count,
            praise_count, comments_count, reposts_count, entertainments_count,
            posted_at, posted_date, scraped_date, ocr_text,
            poster_first_name, poster_last_name, poster_headline, poster_image_url,
            poster_linkedin_url, poster_public_id, article_title, article_subtitle,
            article_target_url, article_description, reshared, resharer_comment
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);"""

        conn = None
        try:
            conn = self.get_db_connection()
            cur = conn.cursor()
            
            for post in posts:
                # Extract poster information
                poster = post.get('poster', {})
                
                # Determine primary media for backward compatibility
                primary_media_type = None
                primary_media_url = None
                
                if post.get('images'):
                    primary_media_type = 'image'
                    primary_media_url = post['images'][0].get('url') if post['images'] else None
                elif post.get('video'):
                    primary_media_type = 'video'
                    primary_media_url = post['video'].get('stream_url')
                elif post.get('document'):
                    primary_media_type = 'document'
                    primary_media_url = post['document'].get('url')

                # Map API fields to database fields
                post_data = (
                    post.get('urn', ''),                                    # urn
                    profile_id,                                             # profile_id
                    post.get('text', ''),                                   # text
                    None,                                                   # cleaned_text
                    None,                                                   # category
                    primary_media_type,                                     # media_type
                    primary_media_url,                                      # media_url
                    post.get('post_url', ''),                               # post_url
                    None,                                                   # processed_post_text
                    post.get('num_reactions', 0),                           # total_reaction_count
                    post.get('num_likes', 0),                               # like_count
                    post.get('num_appreciations', 0),                       # appreciation_count
                    post.get('num_empathy', 0),                             # empathy_count
                    post.get('num_interests', 0),                           # interest_count
                    post.get('num_praises', 0),                             # praise_count
                    post.get('num_comments', 0),                            # comments_count
                    post.get('num_reposts', 0),                             # reposts_count
                    post.get('num_entertainments', 0),                      # entertainments_count
                    post.get('time', ''),                                   # posted_at
                    post.get('posted', ''),                                 # posted_date
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),  # scraped_date
                    None,                                                   # ocr_text
                    poster.get('first', ''),                                # poster_first_name
                    poster.get('last', ''),                                 # poster_last_name
                    poster.get('headline', ''),                             # poster_headline
                    poster.get('image_url', ''),                            # poster_image_url
                    poster.get('linkedin_url', ''),                         # poster_linkedin_url
                    poster.get('public_id', ''),                            # poster_public_id
                    post.get('article_title', ''),                          # article_title
                    post.get('article_subtitle', ''),                       # article_subtitle
                    post.get('article_target_url', ''),                     # article_target_url
                    post.get('article_description', ''),                    # article_description
                    post.get('reshared', False),                            # reshared
                    post.get('resharer_comment', '')                        # resharer_comment
                )

                cur.execute(insert_sql, post_data)
                
                # Get the post_id for media extraction
                post_id = cur.lastrowid
                if post_id:
                    # Extract and save media
                    media_items = self._extract_media(post, post_id)
                    if media_items:
                        self._save_media(media_items, cur)

            conn.commit()
            self.logger.info(f"Saved {len(posts)} posts (profile_id={profile_id})")
            
        except Exception as e:
            self.logger.error(f"Database error while saving posts: {str(e)}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                conn.close()

    def auto_promote_no_posts_profile(self, profile_id: int, username: str, status: str):
        """Auto-promote profiles with no posts to week3_connection."""
        try:
            if not self.pipeline_manager:
                # Create pipeline manager if not available
                from pipeline_manager import SimplifiedPipelineManager
                self.pipeline_manager = SimplifiedPipelineManager()
            
            # Only auto-promote if currently in week1 or week2
            if status in ['week1_likes', 'week2_comments']:
                self.logger.info(f"Auto-promoting {username} (profile_id: {profile_id}) from {status} to week3_connection (no posts found)")
                
                conn = self.get_db_connection()
                cursor = conn.cursor()
                
                # Update status and clear daily slot
                cursor.execute("""
                    UPDATE profiles 
                    SET status = 'week3_connection', 
                        daily_slot = NULL,
                        last_action_date = DATE('now')
                    WHERE profile_id = ?
                """, (profile_id,))
                
                conn.commit()
                conn.close()
                
                self.logger.info(f"✅ Successfully auto-promoted {username} to week3_connection")
                return True
        except Exception as e:
            self.logger.error(f"Error auto-promoting profile {profile_id}: {e}")
            return False
        
        return False

    def run(self):
        """Main execution with pipeline-prioritized scraping."""
        self.logger.info("Starting pipeline-prioritized LinkedInScraper run...")
        
        profile_to_scrape = None
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Priority 1: People in active pipeline stages who need fresh posts
            cursor.execute("""
                SELECT p.profile_id, p.username, p.profile_url, p.status,
                       COUNT(po.post_id) as recent_posts
                FROM profiles p
                LEFT JOIN posts po ON p.profile_id = po.profile_id 
                    AND po.scraped_date >= date('now', '-7 days')
                WHERE p.profile_url IS NOT NULL 
                  AND p.status IN ('week1_likes', 'week2_comments', 'week3_connection')
                GROUP BY p.profile_id
                HAVING recent_posts < 3  -- Need more recent posts
                ORDER BY 
                    CASE p.status 
                        WHEN 'week1_likes' THEN 1
                        WHEN 'week2_comments' THEN 2 
                        WHEN 'week3_connection' THEN 3
                    END,
                    p.job_title_score DESC,
                    recent_posts ASC
                LIMIT 1
            """)
            profile_to_scrape = cursor.fetchone()
            
            # Priority 2: Pipeline people never scraped
            if not profile_to_scrape:
                cursor.execute("""
                    SELECT p.profile_id, p.username, p.profile_url, p.status
                    FROM profiles p
                    LEFT JOIN posts po ON p.profile_id = po.profile_id
                    WHERE p.profile_url IS NOT NULL 
                      AND p.status IN ('week1_likes', 'week2_comments', 'week3_connection')
                      AND po.profile_id IS NULL
                    ORDER BY p.job_title_score DESC, p.profile_id
                    LIMIT 1
                """)
                profile_to_scrape = cursor.fetchone()
            
            # Priority 3: Maintenance people (original round-robin logic)
            if not profile_to_scrape:
                cursor.execute("""
                    SELECT p.profile_id, p.username, p.profile_url, p.status
                    FROM profiles p
                    WHERE p.profile_url IS NOT NULL 
                      AND p.status = 'maintenance'
                    ORDER BY (
                        SELECT MAX(scraped_date) 
                        FROM posts 
                        WHERE profile_id = p.profile_id
                    ) ASC NULLS FIRST
                    LIMIT 1
                """)
                profile_to_scrape = cursor.fetchone()
                
        except Exception as e:
            self.logger.error(f"Error selecting profile: {str(e)}")
        finally:
            if conn:
                conn.close()

        if not profile_to_scrape:
            self.logger.warning("No profiles found to scrape.")
            return

        # Process selected profile
        profile_id, username, profile_url = profile_to_scrape[:3]
        status = profile_to_scrape[3] if len(profile_to_scrape) > 3 else "unknown"
        
        self.logger.info(f"Selected profile: {username} (id={profile_id}, status={status})")
        
        # Rest of method remains the same...
        posts = self.fetch_linkedin_posts(profile_url=profile_url)
        
        if posts:
            self.save_posts(posts, profile_id)
            self.logger.info(f"Successfully processed {len(posts)} posts for {username}")
        else:
            self.logger.info(f"No posts found for '{username}'.")
            self.auto_promote_no_posts_profile(profile_id, username, status)

        self.logger.info("LinkedInScraper run completed (1 API call used).")

    def run_pipeline_batch(self, max_api_calls: int):
        """Execute scraping for multiple pipeline profiles.
        
        Args:
            max_api_calls: Maximum number of API calls to make (from orchestrator config)
        """
        self.logger.info(f"Starting pipeline batch scraper (max {max_api_calls} API calls)...")
        
        profiles_to_scrape = []
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Priority 1: People in active pipeline stages who need fresh posts
            cursor.execute(f"""
                SELECT p.profile_id, p.username, p.profile_url, p.status,
                       COUNT(po.post_id) as recent_posts
                FROM profiles p
                LEFT JOIN posts po ON p.profile_id = po.profile_id 
                    AND po.scraped_date >= date('now', '-7 days')
                WHERE p.profile_url IS NOT NULL 
                  AND p.status IN ('week1_likes', 'week2_comments', 'week3_connection')
                GROUP BY p.profile_id
                HAVING recent_posts < 3  -- Need more recent posts
                ORDER BY 
                    CASE p.status 
                        WHEN 'week1_likes' THEN 1
                        WHEN 'week2_comments' THEN 2 
                        WHEN 'week3_connection' THEN 3
                    END,
                    p.job_title_score DESC,
                    recent_posts ASC
                LIMIT {max_api_calls}
            """)
            profiles_batch_1 = cursor.fetchall()
            profiles_to_scrape.extend(profiles_batch_1)
            
            # Priority 2: Pipeline people never scraped (if we have slots left)
            remaining_slots = max_api_calls - len(profiles_to_scrape)
            if remaining_slots > 0:
                cursor.execute(f"""
                    SELECT p.profile_id, p.username, p.profile_url, p.status
                    FROM profiles p
                    LEFT JOIN posts po ON p.profile_id = po.profile_id
                    WHERE p.profile_url IS NOT NULL 
                      AND p.status IN ('week1_likes', 'week2_comments', 'week3_connection')
                      AND po.profile_id IS NULL
                      AND p.profile_id NOT IN ({','.join(['?' for _ in profiles_to_scrape])})
                    ORDER BY p.job_title_score DESC, p.profile_id
                    LIMIT {remaining_slots}
                """, [p[0] for p in profiles_to_scrape])
                profiles_batch_2 = cursor.fetchall()
                profiles_to_scrape.extend(profiles_batch_2)
                
        except Exception as e:
            self.logger.error(f"Error selecting profiles for batch: {str(e)}")
        finally:
            if conn:
                conn.close()

        if not profiles_to_scrape:
            self.logger.warning("No pipeline profiles found for batch scraping.")
            return 0

        # Process each profile
        successful_scrapes = 0
        auto_promotions = 0
        
        for profile_data in profiles_to_scrape:
            profile_id, username, profile_url = profile_data[:3]
            status = profile_data[3] if len(profile_data) > 3 else "unknown"
            
            self.logger.info(f"Processing profile {successful_scrapes + 1}/{len(profiles_to_scrape)}: {username} (id={profile_id}, status={status})")
            
            posts = self.fetch_linkedin_posts(profile_url=profile_url)
            
            if posts and len(posts) > 0:
                self.save_posts(posts, profile_id)
                self.logger.info(f"✅ Successfully scraped {len(posts)} posts for {username}")
                successful_scrapes += 1
            else:
                self.logger.warning(f"❌ No posts found for '{username}' - auto-promoting to week3_connection")
                if self.auto_promote_no_posts_profile(profile_id, username, status):
                    auto_promotions += 1

        self.logger.info(f"Batch scraping completed: {successful_scrapes}/{len(profiles_to_scrape)} successful scrapes, {auto_promotions} auto-promotions")
        return successful_scrapes


if __name__ == "__main__":
    db_path = "linkedin_project_db.sqlite3"
    api_key = "fb65b935a5msh9e0581a88e0d61fp16d490jsna3c556318665"
    
    scraper = LinkedInScraper(db_path, api_key)
    
    # Choose between single run (original) or batch processing
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "batch":
        max_calls = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        scraper.run_pipeline_batch(max_calls)
    else:
        scraper.run()  # Original single API call behavior
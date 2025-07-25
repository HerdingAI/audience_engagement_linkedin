#!/usr/bin/env python3
"""
Post Scraper - Standalone Script
Purpose: Scrape LinkedIn posts for profiles and manage pre-qualification logic
Usage: 
    python post_scraper.py [--max-profiles=5] [--delay=2]
"""

import os
import sys
import sqlite3
import requests
import json
import time
import logging
import argparse
from datetime import datetime, timezone, date
from typing import List, Dict, Optional, Tuple
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('post_scraper.log')
    ]
)
logger = logging.getLogger(__name__)

# Database and API configuration
DB_PATH = "linkedin_project_db.sqlite3"
API_KEY = "fb65b935a5msh9e0581a88e0d61fp16d490jsna3c556318665"  # RapidAPI key

class PostScraper:
    def __init__(self, db_path: str = DB_PATH, api_key: str = API_KEY):
        """Initialize the post scraper."""
        self.db_path = db_path
        self.api_key = api_key
        self.headers = {
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "real-time-data-enrichment.p.rapidapi.com"
        }
        self._setup_database()
        
    def _setup_database(self):
        """Ensure required database tables exist."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Create posts table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS posts (
                    post_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    urn TEXT,
                    profile_id INTEGER NOT NULL,
                    text TEXT,
                    cleaned_text TEXT,
                    category TEXT,
                    media_type TEXT,
                    media_url TEXT,
                    post_url TEXT,
                    processed_post_text TEXT,
                    total_reaction_count INTEGER DEFAULT 0,
                    like_count INTEGER DEFAULT 0,
                    appreciation_count INTEGER DEFAULT 0,
                    empathy_count INTEGER DEFAULT 0,
                    interest_count INTEGER DEFAULT 0,
                    praise_count INTEGER DEFAULT 0,
                    comments_count INTEGER DEFAULT 0,
                    reposts_count INTEGER DEFAULT 0,
                    entertainments_count INTEGER DEFAULT 0,
                    posted_at TEXT,
                    posted_date TEXT,
                    scraped_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ocr_text TEXT,
                    poster_first_name TEXT,
                    poster_last_name TEXT,
                    poster_headline TEXT,
                    poster_image_url TEXT,
                    poster_linkedin_url TEXT,
                    poster_public_id TEXT,
                    article_title TEXT,
                    article_subtitle TEXT,
                    article_target_url TEXT,
                    article_description TEXT,
                    reshared BOOLEAN DEFAULT 0,
                    resharer_comment TEXT,
                    share_url TEXT,
                    content_type TEXT,
                    posted_date_timestamp INTEGER,
                    reposted BOOLEAN DEFAULT 0,
                    FOREIGN KEY (profile_id) REFERENCES profiles (profile_id)
                )
            """)
            
            # Create media table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS media (
                    media_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    media_url TEXT,
                    media_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES posts (post_id)
                )
            """)
            
            # Create profiles table if it doesn't exist (minimal version for standalone operation)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    username TEXT,
                    profile_url TEXT NOT NULL,
                    company_name TEXT,
                    job_title TEXT,
                    status TEXT DEFAULT 'not_started',
                    connection_status TEXT DEFAULT 'prospect',
                    job_title_score INTEGER DEFAULT 0,
                    priority_score INTEGER DEFAULT 0,
                    last_action_date DATE,
                    weekly_batch INTEGER,
                    daily_slot INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(profile_url, username)
                )
            """)
            
            conn.commit()
            conn.close()
            logger.info("Database setup completed")
            
        except Exception as e:
            logger.error(f"Database setup error: {e}")
            raise

    def get_db_connection(self) -> sqlite3.Connection:
        """Create and return a database connection."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Database connection error: {e}")
            raise

    def extract_username_from_url(self, profile_url: str) -> Optional[str]:
        """Extract username from LinkedIn profile URL."""
        try:
            if '/in/' in profile_url:
                username = profile_url.split('/in/')[-1].rstrip('/')
                # Remove any query parameters
                if '?' in username:
                    username = username.split('?')[0]
                return username
            else:
                logger.error(f"Invalid LinkedIn URL format: {profile_url}")
                return None
        except Exception as e:
            logger.error(f"Error extracting username from URL {profile_url}: {e}")
            return None

    def get_profiles_for_scraping(self) -> List[Dict]:
        """Get profiles that need post scraping (status = 'not_started')."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                 SELECT  profile_id, first_name,
                    last_name,
                    username,
                    profile_url
                    FROM
                    profiles
                    WHERE
                    status = 'maintenance'
                AND connection_status like 'current_connection'
				AND job_title like '%product%'
                 AND job_title_score > 0
               AND (
                  last_action_date < date('now', '-180 days')
                   OR last_action_date IS NULL
                 )
                    AND profile_url IS NOT NULL
                    ORDER BY
                    job_title_score DESC,
                    profile_id;
            """)
            
            profiles = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            logger.info(f"Found {len(profiles)} profiles ready for scraping")
            return profiles
            
        except Exception as e:
            logger.error(f"Error getting profiles for scraping: {e}")
            return []

    def fetch_linkedin_posts(self, profile_url: str) -> List[Dict]:
        """Fetch LinkedIn posts for a given profile URL using RapidAPI."""
        username = self.extract_username_from_url(profile_url)
        if not username:
            logger.error(f"Could not extract username from URL: {profile_url}")
            return []

        url = "https://real-time-data-enrichment.p.rapidapi.com/get-profile-posts"
        
        query_params = {
            "username": username,
            "start": "0"
        }

        logger.info(f"Fetching posts for username: {username}")
        
        try:
            response = requests.get(url, headers=self.headers, params=query_params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                logger.debug(f"API response data: {data}")
                
                if data.get("success"):
                    posts = data.get("data", [])
                    logger.info(f"Successfully fetched {len(posts)} posts for {username}")
                    return posts
                else:
                    logger.warning(f"API response indicates failure: {data.get('message')}")
                    return []
            else:
                logger.error(
                    f"Error fetching posts for '{profile_url}': "
                    f"{response.status_code} - {response.text}"
                )
                return []
        except Exception as e:
            logger.error(f"Exception while fetching posts for {profile_url}: {str(e)}")
            return []

    def extract_media(self, post: Dict, post_id: int) -> List[Dict]:
        """Extract media from post for storage in media table."""
        media_items = []
        
        try:
            # Handle images (nested arrays)
            if post.get('images'):
                for image_group in post['images']:
                    if isinstance(image_group, list):
                        for image in image_group:
                            media_items.append({
                                'post_id': post_id,
                                'media_url': image.get('url'),
                                'media_type': 'image'
                            })
            
            # Handle single image array
            if post.get('image'):
                for image in post['image']:
                    media_items.append({
                        'post_id': post_id,
                        'media_url': image.get('url'),
                        'media_type': 'image'
                    })
            
            # Handle video (array)
            if post.get('video'):
                for video in post['video']:
                    media_items.append({
                        'post_id': post_id,
                        'media_url': video.get('url'),
                        'media_type': 'video'
                    })
            
            # Handle document
            if post.get('document') and post['document'].get('TranscribedDocumentUrl'):
                media_items.append({
                    'post_id': post_id,
                    'media_url': post['document'].get('TranscribedDocumentUrl'),
                    'media_type': 'document'
                })
                
        except Exception as e:
            logger.error(f"Error extracting media: {str(e)}")
        
        return media_items

    def save_media(self, media_items: List[Dict], cursor) -> None:
        """Save media items to the media table."""
        if not media_items:
            return

        insert_sql = """INSERT OR IGNORE INTO media (
            post_id, media_url, media_type
        ) VALUES (?, ?, ?)"""

        try:
            for media in media_items:
                cursor.execute(insert_sql, (
                    media['post_id'],
                    media['media_url'],
                    media['media_type']
                ))
            
            logger.debug(f"Saved {len(media_items)} media items")
        except Exception as e:
            logger.error(f"Error saving media: {str(e)}")
            raise

    def save_posts(self, posts: List[Dict], profile_id: int) -> int:
        """Save posts to the database and return number of posts saved."""
        if not posts:
            logger.info("No posts to save")
            return 0

        insert_sql = """INSERT OR IGNORE INTO posts (
            urn, profile_id, text, cleaned_text, category, media_type, 
            media_url, post_url, processed_post_text, total_reaction_count,
            like_count, appreciation_count, empathy_count, interest_count,
            praise_count, comments_count, reposts_count, entertainments_count,
            posted_at, posted_date, scraped_date, ocr_text,
            poster_first_name, poster_last_name, poster_headline, poster_image_url,
            poster_linkedin_url, poster_public_id, article_title, article_subtitle,
            article_target_url, article_description, reshared, resharer_comment,
            share_url, content_type, posted_date_timestamp, reposted
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""

        conn = None
        posts_saved = 0
        
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            for post in posts:
                # Extract author information
                author = post.get('author', {})
                
                # Get profile picture URL
                profile_pictures = author.get('profilePictures', [])
                profile_pic_url = profile_pictures[0].get('url') if profile_pictures else ''
                
                # Determine primary media for backward compatibility
                primary_media_type = None
                primary_media_url = None
                
                if post.get('images'):
                    primary_media_type = 'image'
                    if post['images'] and isinstance(post['images'][0], list):
                        primary_media_url = post['images'][0][0].get('url') if post['images'][0] else None
                    elif post['images']:
                        primary_media_url = post['images'][0].get('url')
                elif post.get('image'):
                    primary_media_type = 'image'
                    primary_media_url = post['image'][0].get('url') if post['image'] else None
                elif post.get('video'):
                    primary_media_type = 'video'
                    primary_media_url = post['video'][0].get('url') if post['video'] else None
                elif post.get('document'):
                    primary_media_type = 'document'
                    primary_media_url = post['document'].get('TranscribedDocumentUrl')

                # Handle article information
                article = post.get('article', {})
                
                # Map API fields to database fields
                post_data = (
                    post.get('urn', ''),                                    # urn
                    profile_id,                                             # profile_id
                    post.get('text', ''),                                   # text
                    None,                                                   # cleaned_text
                    None,                                                   # category
                    primary_media_type,                                     # media_type
                    primary_media_url,                                      # media_url
                    post.get('postUrl', ''),                                # post_url
                    None,                                                   # processed_post_text
                    post.get('totalReactionCount', 0),                      # total_reaction_count
                    post.get('likeCount', 0),                               # like_count
                    post.get('appreciationCount', 0),                       # appreciation_count
                    post.get('empathyCount', 0),                            # empathy_count
                    post.get('InterestCount', 0),                           # interest_count
                    post.get('praiseCount', 0),                             # praise_count
                    post.get('commentsCount', 0),                           # comments_count
                    post.get('repostsCount', 0),                            # reposts_count
                    post.get('funnyCount', 0),                              # entertainments_count
                    post.get('postedAt', ''),                               # posted_at
                    post.get('postedDate', ''),                             # posted_date
                    datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),  # scraped_date
                    None,                                                   # ocr_text
                    author.get('firstName', ''),                            # poster_first_name
                    author.get('lastName', ''),                             # poster_last_name
                    author.get('headline', ''),                             # poster_headline
                    profile_pic_url,                                        # poster_image_url
                    author.get('url', ''),                                  # poster_linkedin_url
                    author.get('username', ''),                             # poster_public_id
                    article.get('title', ''),                               # article_title
                    article.get('subtitle', ''),                            # article_subtitle
                    article.get('link', ''),                                # article_target_url
                    '',                                                     # article_description
                    bool(post.get('resharedPost')),                         # reshared
                    post.get('text', '') if post.get('resharedPost') else '',  # resharer_comment
                    post.get('shareUrl', ''),                               # share_url
                    post.get('contentType', ''),                            # content_type
                    post.get('postedDateTimestamp', 0),                     # posted_date_timestamp
                    post.get('reposted', False)                             # reposted
                )

                cursor.execute(insert_sql, post_data)
                
                # Check if the post was actually inserted (not a duplicate)
                if cursor.rowcount > 0:
                    posts_saved += 1
                    post_id = cursor.lastrowid
                    
                    # Extract and save media if post was inserted
                    if post_id:
                        media_items = self.extract_media(post, post_id)
                        if media_items:
                            self.save_media(media_items, cursor)

            conn.commit()
            logger.info(f"Saved {posts_saved} new posts for profile_id={profile_id}")
            return posts_saved
            
        except Exception as e:
            logger.error(f"Database error while saving posts: {str(e)}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()

    def check_recent_posts(self, profile_id: int, days_threshold: int = 21) -> bool:
        """Check if profile has posts newer than the threshold."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM posts 
                WHERE profile_id = ?
                AND posted_date > datetime('now', '-{} days')
            """.format(days_threshold), (profile_id,))
            
            result = cursor.fetchone()
            conn.close()
            
            has_recent = result['count'] > 0
            logger.debug(f"Profile {profile_id} has recent posts (<{days_threshold} days): {has_recent}")
            return has_recent
            
        except Exception as e:
            logger.error(f"Error checking recent posts for profile {profile_id}: {e}")
            return False

    def update_profile_status(self, profile_id: int, new_status: str, reason: str = "") -> bool:
        """Update profile status after scraping."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE profiles 
                SET status = ?, last_action_date = date('now')
                WHERE profile_id = ?
            """, (new_status, profile_id))
            
            updated = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            if updated:
                logger.info(f"Updated profile {profile_id} to status '{new_status}'. {reason}")
            else:
                logger.warning(f"Failed to update profile {profile_id} status")
            
            return updated
            
        except Exception as e:
            logger.error(f"Error updating profile {profile_id} status: {e}")
            return False

    def scrape_profile(self, profile: Dict) -> Dict:
        """Scrape posts for a single profile and return results."""
        profile_id = profile['profile_id']
        profile_url = profile['profile_url']
        name = f"{profile['first_name']} {profile['last_name']}"
        
        logger.info(f"Scraping profile: {name} (ID: {profile_id})")
        
        result = {
            'profile_id': profile_id,
            'name': name,
            'posts_fetched': 0,
            'posts_saved': 0,
            'has_recent_posts': False,
            'new_status': None,
            'success': False
        }
        
        try:
            # Fetch posts from LinkedIn API
            posts = self.fetch_linkedin_posts(profile_url)
            result['posts_fetched'] = len(posts)
            
            if posts:
                # Save posts to database
                posts_saved = self.save_posts(posts, profile_id)
                result['posts_saved'] = posts_saved
                
                # Check if profile has recent posts (< 21 days)
                has_recent = self.check_recent_posts(profile_id, days_threshold=21)
                result['has_recent_posts'] = has_recent
                
                if has_recent:
                    # Profile has recent content - move to week1_liking
                    self.update_profile_status(profile_id, 'week1_liking', "Has recent posts")
                    result['new_status'] = 'week1_liking'
                else:
                    # No recent content - skip to connections
                    self.update_profile_status(profile_id, 'maintenance', "No recent posts")
                    result['new_status'] = 'maintenance'
            else:
                # No posts found - skip to connections
                self.update_profile_status(profile_id, 'maintenance', "No posts found")
                result['new_status'] = 'maintenance'

            result['success'] = True
            logger.info(f"✅ Completed scraping {name}: {result['posts_saved']} posts, status: {result['new_status']}")
            
        except Exception as e:
            logger.error(f"❌ Error scraping profile {name}: {e}")
            result['error'] = str(e)
        
        return result

    def scrape_batch(self, max_profiles: int = 15, delay_seconds: int = 2) -> Dict:
        """Scrape posts for a batch of profiles."""
        logger.info(f"Starting batch scraping (max {max_profiles} profiles, {delay_seconds}s delay)")
        
        # Get profiles to scrape
        profiles = self.get_profiles_for_scraping()
        
        if not profiles:
            logger.info("No profiles found that need scraping")
            return {
                'profiles_processed': 0,
                'profiles_scraped': 0,
                'total_posts_saved': 0,
                'profiles_to_week1': 0,
                'profiles_to_week3': 0,
                'results': []
            }
        
        # Limit to max_profiles
        profiles_to_process = profiles[:max_profiles]
        logger.info(f"Processing {len(profiles_to_process)} profiles")
        
        batch_results = {
            'profiles_processed': len(profiles_to_process),
            'profiles_scraped': 0,
            'total_posts_saved': 0,
            'profiles_to_week1': 0,
            'profiles_to_week3': 0,
            'results': []
        }
        
        for i, profile in enumerate(profiles_to_process):
            logger.info(f"Processing profile {i+1}/{len(profiles_to_process)}")
            
            # Scrape the profile
            result = self.scrape_profile(profile)
            batch_results['results'].append(result)
            
            if result['success']:
                batch_results['profiles_scraped'] += 1
                batch_results['total_posts_saved'] += result['posts_saved']
                
                if result['new_status'] == 'week1_liking':
                    batch_results['profiles_to_week1'] += 1
                elif result['new_status'] == 'week3_invitation':
                    batch_results['profiles_to_week3'] += 1
            
            # Apply delay between requests (except after the last one)
            if i < len(profiles_to_process) - 1:
                logger.info(f"Applying {delay_seconds}s delay...")
                time.sleep(delay_seconds)
        
        logger.info(f"Batch scraping completed: {batch_results}")
        return batch_results

    def get_scraping_stats(self) -> Dict:
        """Get current scraping statistics."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            stats = {}
            
            # Profiles by status
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM profiles 
                GROUP BY status
            """)
            status_counts = {}
            for row in cursor.fetchall():
                status_counts[row['status']] = row['count']
            stats['status_breakdown'] = status_counts
            
            # Total posts
            cursor.execute("SELECT COUNT(*) as count FROM posts")
            stats['total_posts'] = cursor.fetchone()['count']
            
            # Posts by profile status
            cursor.execute("""
                SELECT p.status, COUNT(po.post_id) as post_count
                FROM profiles p
                LEFT JOIN posts po ON p.profile_id = po.profile_id
                GROUP BY p.status
            """)
            posts_by_status = {}
            for row in cursor.fetchall():
                posts_by_status[row['status']] = row['post_count']
            stats['posts_by_status'] = posts_by_status
            
            # Recent scraping activity
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM profiles 
                WHERE last_action_date = date('now')
            """)
            stats['scraped_today'] = cursor.fetchone()['count']
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"Error getting scraping stats: {e}")
            return {}

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="LinkedIn Post Scraper")
    parser.add_argument('--max-profiles', type=int, default=5, 
                       help='Maximum number of profiles to scrape (default: 5)')
    parser.add_argument('--delay', type=int, default=2,
                       help='Delay in seconds between API calls (default: 2)')
    parser.add_argument('--stats-only', action='store_true',
                       help='Show statistics only, do not scrape')
    
    args = parser.parse_args()
    
    try:
        # Initialize scraper
        scraper = PostScraper()
        
        # Show current stats
        logger.info("Current scraping statistics:")
        stats = scraper.get_scraping_stats()
        
        if stats.get('status_breakdown'):
            logger.info("Profile status breakdown:")
            for status, count in stats['status_breakdown'].items():
                logger.info(f"  {status}: {count}")
        
        logger.info(f"Total posts in database: {stats.get('total_posts', 0)}")
        logger.info(f"Profiles scraped today: {stats.get('scraped_today', 0)}")
        
        if args.stats_only:
            return
        
        # Run batch scraping
        results = scraper.scrape_batch(
            max_profiles=args.max_profiles,
            delay_seconds=args.delay
        )
        
        # Display results
        print(f"\n{'='*60}")
        print("SCRAPING RESULTS")
        print(f"{'='*60}")
        print(f"Profiles processed: {results['profiles_processed']}")
        print(f"Profiles successfully scraped: {results['profiles_scraped']}")
        print(f"Total posts saved: {results['total_posts_saved']}")
        print(f"Profiles moved to week1_liking: {results['profiles_to_week1']}")
        print(f"Profiles moved to week3_invitation: {results['profiles_to_week3']}")
        
        if results['profiles_scraped'] > 0:
            print("✅ Scraping completed successfully!")
        else:
            print("⚠️ No profiles were successfully scraped")
        
        # Show individual results if requested
        if len(results['results']) <= 5:  # Only show details for small batches
            print(f"\nIndividual Results:")
            for result in results['results']:
                status = "✅" if result['success'] else "❌"
                print(f"{status} {result['name']}: {result['posts_saved']} posts → {result['new_status']}")
        
    except Exception as e:
        logger.error(f"Post scraper failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
"""
Comment Poster - Standalone Script
Purpose: Post generated comments to LinkedIn for profiles in week2_commenting status and advance them to week3_invitation
Usage: 
    python comment_poster.py [--max-comments=25] [--delay=30]
"""

import os
import sys
import sqlite3
import requests
import json
import time
import logging
import argparse
import random
from datetime import datetime, date
from typing import Dict, Optional, List, Tuple
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('comment_poster.log')
    ]
)
logger = logging.getLogger(__name__)

# Database and LinkedIn API configuration
DB_PATH = "linkedin_project_db.sqlite3"

# LinkedIn API credentials
CLIENT_ID = "786rwpg272olkl"
CLIENT_SECRET = "WPL_AP1.y2jmsNflI7Pc12SX.qsruIQ=="
ACCESS_TOKEN = "AQWThaYqZiuECBVR1YvnofTYp21b_7hY37FwczmPYi_P7AI8o8-9-m0V15w943j5znGhRIRjmc4V_skIh8K6QMQwQ89SD5mNIZp0PHcwpSWz_E5VaUGmgLyBq-P5DknWFBo3uu8LPaHf3PegPtJjOHqeSDD_gqjkOcq3Q368iZeZhdZYpuX8jXRsFGOSkmhvGiYk3PNvfWnE3FfyL7gVchdv_AkISvIhwqtZ16uLH-GJUfiW4K3sJgm5ei7XOGbLav3MIg8if43mzO4DmIrffyrXrZ5Ummv4Qm82UeHqjww99AJvjpwiMvOqoIHI2x3Nq5GgdfN0sVqrGzSXC3ysmUW1D0FO-A"
LINKEDIN_PROFILE_ID = "urn:li:person:BWhT9OIznT"

class CommentPoster:
    def __init__(self, db_path: str = DB_PATH):
        """Initialize the comment poster."""
        self.db_path = db_path
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self._setup_database()
        
    def _setup_database(self):
        """Ensure required database tables and columns exist."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Create profiles table if it doesn't exist
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
                    liked_to_linkedin_at TIMESTAMP,
                    linkedin_like_id TEXT,
                    linkedin_like_urn TEXT,
                    is_post_liked BOOLEAN DEFAULT FALSE,
                    like_failed BOOLEAN DEFAULT FALSE,
                    FOREIGN KEY (profile_id) REFERENCES profiles (profile_id)
                )
            """)
            
            # Create comments table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    generated_comment TEXT NOT NULL,
                    status TEXT DEFAULT 'GENERATED',
                    is_comment_posted BOOLEAN DEFAULT FALSE,
                    posted_to_linkedin_at TIMESTAMP,
                    linkedin_comment_id TEXT,
                    linkedin_comment_urn TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES posts (post_id)
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

    def get_headers(self) -> Dict[str, str]:
        """Generate headers for LinkedIn API requests."""
        return {
            "Authorization": f"Bearer {ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

    def get_comments_to_post(self) -> List[Dict]:
        """Get generated comments for profiles in week2_commenting status with recent posts."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Use the exact SQL query specified by the user, modified for comments
            cursor.execute("""
                SELECT profiles.profile_id, profiles.first_name, profiles.last_name,
                       profiles.connection_status,
                       posts.post_id, posts.urn, posts.text, posts.posted_date,
                       comments.comment_id, comments.generated_comment
                FROM profiles
                JOIN posts ON posts.profile_id = profiles.profile_id
                JOIN comments ON comments.post_id = posts.post_id
                WHERE profiles.status = 'week2_commenting'
                AND posts.posted_date > datetime('now', '-30 days')
                  AND comments.status = 'GENERATED'
                  AND comments.is_comment_posted = FALSE
                  AND comments.generated_comment IS NOT NULL
                  AND comments.generated_comment != ''
                  AND posts.urn IS NOT NULL
                  AND posts.urn != ''
                ORDER BY profiles.job_title_score DESC, posts.posted_date DESC
            """)
            
            comments = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            logger.info(f"Found {len(comments)} comments ready for posting")
            return comments
            
        except Exception as e:
            logger.error(f"Error getting comments to post: {e}")
            return []

    def validate_linkedin_credentials(self) -> Dict:
        """Validate LinkedIn credentials and get user info."""
        try:
            url = "https://api.linkedin.com/v2/userinfo"
            headers = self.get_headers()
            
            logger.info("Validating LinkedIn credentials...")
            response = self.session.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                user_data = response.json()
                user_id = user_data.get('sub')
                logger.info(f"LinkedIn validation successful. User ID: {user_id}")
                return {
                    'valid': True,
                    'user_id': user_id,
                    'user_data': user_data
                }
            else:
                logger.error(f"LinkedIn validation failed: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return {'valid': False, 'error': f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"Error validating LinkedIn credentials: {e}")
            return {'valid': False, 'error': str(e)}

    def clean_comment_for_linkedin(self, comment: str) -> str:
        """Clean and prepare comment content for LinkedIn posting."""
        # Remove any problematic characters or formatting
        cleaned = comment.strip()
        
        # Remove markdown code blocks if present
        cleaned = cleaned.replace('```', '').replace('json', '')
        
        # Remove any system prompts or AI artifacts that might be in the comment
        lines = cleaned.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            # Skip empty lines and system-like messages
            if line and not line.startswith('[') and not line.startswith('Note:'):
                cleaned_lines.append(line)
        
        cleaned = ' '.join(cleaned_lines)
        
        # LinkedIn comments have a character limit (typically 1250 characters)
        if len(cleaned) > 1250:
            cleaned = cleaned[:1247] + "..."
            logger.warning("Comment was truncated to fit LinkedIn's character limit")
        
        return cleaned

    def format_post_urn(self, post_urn_or_id: str) -> str:
        """Convert numeric post ID to proper LinkedIn URN format if needed."""
        if post_urn_or_id.startswith('urn:li:'):
            return post_urn_or_id
        
        # Convert numeric ID to activity URN format
        return f"urn:li:activity:{post_urn_or_id}"

    def create_linkedin_comment_payload(self, comment_text: str, post_urn: str, user_id: str) -> Dict:
        """Create the JSON payload for LinkedIn comment API."""
        cleaned_comment = self.clean_comment_for_linkedin(comment_text)
        
        return {
            "actor": f"urn:li:person:{user_id}",
            "object": post_urn,
            "message": {
                "text": cleaned_comment
            }
        }

    def get_comment_endpoint_url(self, post_urn: str) -> str:
        """Generate the comment endpoint URL for a specific post."""
        import urllib.parse
        encoded_urn = urllib.parse.quote(post_urn, safe='')
        return f"https://api.linkedin.com/v2/socialActions/{encoded_urn}/comments"

    def post_comment_to_linkedin(self, comment_text: str, post_urn: str, user_id: str) -> Optional[Dict]:
        """Post comment to LinkedIn using v2 API with enhanced URN handling and retry logic."""
        try:
            formatted_urn = self.format_post_urn(post_urn)
            logger.info(f"Posting comment to LinkedIn for post: {formatted_urn}")
            
            payload = self.create_linkedin_comment_payload(comment_text, formatted_urn, user_id)
            headers = self.get_headers()
            endpoint_url = self.get_comment_endpoint_url(formatted_urn)
            
            # Log comment preview for debugging
            cleaned_comment = self.clean_comment_for_linkedin(comment_text)
            logger.debug(f"Comment preview: {cleaned_comment[:100]}...")
            
            response = self.session.post(
                endpoint_url,
                headers=headers,
                json=payload,
                timeout=30
            )
            
            logger.debug(f"LinkedIn API response status: {response.status_code}")
            
            if response.status_code == 201:
                response_data = response.json() if response.content else {}
                
                # Try different possible header names for comment ID
                comment_id = (response.headers.get('x-linkedin-id') or 
                            response.headers.get('x-restli-id') or 
                            response.headers.get('location', '').split('/')[-1] or
                            'unknown')
                
                logger.info(f"Successfully posted comment to LinkedIn. Comment ID: {comment_id}")
                return {
                    'success': True,
                    'comment_id': comment_id,
                    'response_data': response_data,
                    'urn_used': formatted_urn
                }
            elif response.status_code == 400:
                error_text = response.text
                
                # Handle URN mismatch with retry logic (same as post liker)
                if "is not the same as the actual threadUrn" in error_text:
                    logger.warning(f"URN mismatch for {formatted_urn}. Attempting to extract correct URN.")
                    
                    # Extract correct URN from error message - support multiple formats
                    correct_urn = None
                    
                    # Try different URN patterns
                    patterns = [
                        r'actual threadUrn: (urn:li:activity:\d+)',  # Most common pattern
                        r'actual threadUrn: (urn:li:ugcPost:\d+)',   # Alternative pattern
                        r'(urn:li:activity:\d+)',                    # Fallback activity pattern
                        r'(urn:li:ugcPost:\d+)'                      # Fallback ugcPost pattern
                    ]
                    
                    import re
                    for pattern in patterns:
                        match = re.search(pattern, error_text)
                        if match:
                            correct_urn = match.group(1)
                            logger.info(f"Found correct URN using pattern '{pattern}': {correct_urn}")
                            break
                    
                    if correct_urn:
                        try:
                            # Retry with correct URN
                            retry_payload = self.create_linkedin_comment_payload(comment_text, correct_urn, user_id)
                            retry_endpoint_url = self.get_comment_endpoint_url(correct_urn)
                            
                            retry_response = self.session.post(
                                retry_endpoint_url,
                                headers=headers,
                                json=retry_payload,
                                timeout=30
                            )
                            
                            if retry_response.status_code == 201:
                                retry_data = retry_response.json() if retry_response.content else {}
                                retry_comment_id = (retry_response.headers.get('x-linkedin-id') or
                                                  retry_response.headers.get('x-restli-id') or
                                                  'unknown')
                                
                                logger.info(f"✅ Retry successful with corrected URN. Comment ID: {retry_comment_id}")
                                return {
                                    'success': True,
                                    'comment_id': retry_comment_id,
                                    'response_data': retry_data,
                                    'urn_used': correct_urn
                                }
                            else:
                                logger.error(f"Retry failed: {retry_response.status_code} - {retry_response.text}")
                                return None
                                
                        except Exception as retry_error:
                            logger.error(f"Retry attempt failed: {retry_error}")
                            return None
                    else:
                        logger.error(f"Could not extract correct URN from error: {error_text}")
                        return None
                else:
                    logger.error(f"LinkedIn API error: {response.status_code}")
                    logger.error(f"Response: {error_text}")
                    return None
            else:
                logger.error(f"LinkedIn API error: {response.status_code}")
                logger.error(f"Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error posting comment to LinkedIn: {e}")
            return None

    def mark_comment_as_posted(self, comment_id: int, linkedin_comment_id: str, linkedin_comment_urn: str) -> bool:
        """Mark comment as successfully posted in the database."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE comments
                SET 
                    is_comment_posted = TRUE,
                    posted_to_linkedin_at = CURRENT_TIMESTAMP,
                    linkedin_comment_id = ?,
                    linkedin_comment_urn = ?
                WHERE comment_id = ?
            """, (linkedin_comment_id, linkedin_comment_urn, comment_id))
            
            updated = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            if updated:
                logger.info(f"Marked comment {comment_id} as posted")
            else:
                logger.warning(f"Failed to mark comment {comment_id} as posted")
            
            return updated
            
        except sqlite3.Error as e:
            logger.error(f"Error marking comment {comment_id} as posted: {e}")
            return False

    def mark_comment_as_failed(self, comment_id: int, error_message: str) -> bool:
        """Mark comment as failed to post."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE comments
                SET status = 'FAILED'
                WHERE comment_id = ?
            """, (comment_id,))
            
            updated = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            if updated:
                logger.info(f"Marked comment {comment_id} as failed: {error_message}")
            
            return updated
            
        except sqlite3.Error as e:
            logger.error(f"Error marking comment {comment_id} as failed: {e}")
            return False

    def get_failure_status_for_connection_type(self, connection_status: str) -> str:
        """Determine the correct failure status based on connection type."""
        if connection_status == 'prospect':
            return 'week3_invitation'  # Prospects that fail commenting go to invitations
        elif connection_status == 'current_connection':
            return 'maintenance'  # Current connections that fail go back to maintenance
        else:
            # Default fallback
            logger.warning(f"Unknown connection_status: {connection_status}, defaulting to week3_invitation")
            return 'week3_invitation'

    def update_profile_status(self, profile_id: int, new_status: str, reason: str = "") -> bool:
        """Update profile status after successful comment posting."""
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

    def post_comment(self, comment_data: Dict, user_id: str) -> Dict:
        """Post a single comment and return results."""
        comment_id = comment_data['comment_id']
        post_id = comment_data['post_id']
        profile_id = comment_data['profile_id']
        name = f"{comment_data['first_name']} {comment_data['last_name']}"
        post_urn = comment_data['urn']
        comment_text = comment_data['generated_comment']
        
        result = {
            'comment_id': comment_id,
            'post_id': post_id,
            'profile_id': profile_id,
            'name': name,
            'success': False,
            'profile_updated': False
        }
        
        try:
            logger.info(f"Posting comment {comment_id} for post {post_id} by {name}")
            
            # Attempt to post the comment
            post_response = self.post_comment_to_linkedin(comment_text, post_urn, user_id)
            
            if post_response and post_response.get('success'):
                # Mark comment as posted
                comment_marked = self.mark_comment_as_posted(
                    comment_id,
                    post_response.get('comment_id', 'unknown'),
                    post_response.get('response_data', {}).get('commentUrn', 'unknown')
                )
                
                if comment_marked:
                    # Update profile status to week3_invitation
                    profile_updated = self.update_profile_status(
                        profile_id, 
                        'week3_invitation', 
                        f"Posted comment {comment_id}"
                    )
                    
                    result['success'] = True
                    result['profile_updated'] = profile_updated
                    logger.info(f"✅ Successfully posted comment {comment_id} by {name}")
                else:
                    logger.error(f"Failed to mark comment {comment_id} as posted in database")
            else:
                # Mark comment as failed
                self.mark_comment_as_failed(comment_id, "LinkedIn API error")
                
                # Update profile status based on connection type
                connection_status = comment_data.get('connection_status', 'prospect')
                failure_status = self.get_failure_status_for_connection_type(connection_status)
                
                profile_updated = self.update_profile_status(
                    profile_id, 
                    failure_status, 
                    f"Failed to post comment {comment_id} - moved to {failure_status}"
                )
                
                result['failure_status'] = failure_status
                result['profile_updated'] = profile_updated
                logger.error(f"❌ Failed to post comment {comment_id} by {name} - moved profile to {failure_status}")
                
        except Exception as e:
            logger.error(f"❌ Error posting comment {comment_id}: {e}")
            result['error'] = str(e)
        
        return result

    def post_comments_batch(self, max_comments: int = 25, delay_range: Tuple[int, int] = (30, 90)) -> Dict:
        """Post a batch of comments with human-like delays."""
        logger.info(f"Starting comment posting batch (max {max_comments} comments)")
        
        # Validate credentials
        validation_result = self.validate_linkedin_credentials()
        if not validation_result.get('valid', False):
            logger.error("LinkedIn credentials validation failed")
            return {
                'success': False, 
                'error': validation_result.get('error', 'Invalid credentials'),
                'comments_posted': 0,
                'profiles_advanced': 0
            }
        
        user_id = validation_result.get('user_id')
        if not user_id:
            logger.error("Failed to get user ID from LinkedIn validation")
            return {
                'success': False, 
                'error': 'No user ID',
                'comments_posted': 0,
                'profiles_advanced': 0
            }
        
        # Get comments to post
        comments_to_post = self.get_comments_to_post()
        
        if not comments_to_post:
            logger.info("No comments found that need posting")
            return {
                'success': True,
                'comments_posted': 0,
                'profiles_advanced': 0,
                'message': 'No comments to post'
            }
        
        # Limit to max_comments
        comments_to_process = comments_to_post[:max_comments]
        logger.info(f"Processing {len(comments_to_process)} comments")
        
        batch_results = {
            'success': True,
            'comments_posted': 0,
            'profiles_advanced': 0,
            'errors': [],
            'results': []
        }
        
        for i, comment_data in enumerate(comments_to_process):
            logger.info(f"Processing comment {i+1}/{len(comments_to_process)}")
            
            # Post the comment
            result = self.post_comment(comment_data, user_id)
            batch_results['results'].append(result)
            
            if result['success']:
                batch_results['comments_posted'] += 1
                if result['profile_updated']:
                    batch_results['profiles_advanced'] += 1
            else:
                if 'error' in result:
                    batch_results['errors'].append(result['error'])
            
            # Apply human-like delay between comments (except after the last one)
            if i < len(comments_to_process) - 1:
                # Longer delays for comments to simulate reading and composing
                delay = random.randint(delay_range[0], delay_range[1])
                logger.info(f"Human-like delay: {delay}s...")
                time.sleep(delay)
        
        logger.info(f"Batch commenting completed: {batch_results['comments_posted']} comments, {batch_results['profiles_advanced']} profiles advanced")
        return batch_results

    def get_commenting_stats(self) -> Dict:
        """Get current commenting statistics."""
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
            
            # Comments stats
            cursor.execute("SELECT COUNT(*) as count FROM comments WHERE status = 'GENERATED'")
            stats['total_generated_comments'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM comments WHERE is_comment_posted = TRUE")
            stats['posted_comments'] = cursor.fetchone()['count']
            
            cursor.execute("SELECT COUNT(*) as count FROM comments WHERE status = 'FAILED'")
            stats['failed_comments'] = cursor.fetchone()['count']
            
            # Week2 commenting candidates
            cursor.execute("""
                SELECT COUNT(DISTINCT profiles.profile_id) as count
                FROM profiles
                JOIN posts ON posts.profile_id = profiles.profile_id
                JOIN comments ON comments.post_id = posts.post_id
                WHERE profiles.status = 'week2_commenting'
                  AND date(posts.posted_date) > date('now', '-30 days')
                  AND comments.status = 'GENERATED'
                  AND comments.is_comment_posted = FALSE
                  AND comments.generated_comment IS NOT NULL
                  AND comments.generated_comment != ''
                  AND posts.urn IS NOT NULL
                  AND posts.urn != ''
            """)
            stats['week2_candidates'] = cursor.fetchone()['count']
            
            # Last posted date
            cursor.execute("""
                SELECT posted_to_linkedin_at 
                FROM comments 
                WHERE is_comment_posted = TRUE 
                ORDER BY posted_to_linkedin_at DESC 
                LIMIT 1
            """)
            result = cursor.fetchone()
            stats['last_posted'] = result['posted_to_linkedin_at'] if result else None
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"Error getting commenting stats: {e}")
            return {}

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="LinkedIn Comment Poster")
    parser.add_argument('--max-comments', type=int, default=25,
                       help='Maximum number of comments to post (default: 25)')
    parser.add_argument('--min-delay', type=int, default=30,
                       help='Minimum delay between comments in seconds (default: 30)')
    parser.add_argument('--max-delay', type=int, default=90,
                       help='Maximum delay between comments in seconds (default: 90)')
    parser.add_argument('--stats-only', action='store_true',
                       help='Show statistics only, do not post comments')
    
    args = parser.parse_args()
    
    try:
        # Initialize poster
        poster = CommentPoster()
        
        # Show current stats
        logger.info("Current commenting statistics:")
        stats = poster.get_commenting_stats()
        
        if stats.get('status_breakdown'):
            logger.info("Profile status breakdown:")
            for status, count in stats['status_breakdown'].items():
                logger.info(f"  {status}: {count}")
        
        logger.info(f"Total generated comments: {stats.get('total_generated_comments', 0)}")
        logger.info(f"Comments already posted: {stats.get('posted_comments', 0)}")
        logger.info(f"Failed comments: {stats.get('failed_comments', 0)}")
        logger.info(f"Week2 candidates ready for commenting: {stats.get('week2_candidates', 0)}")
        
        if stats.get('last_posted'):
            logger.info(f"Last posted: {stats['last_posted']}")
        
        if args.stats_only:
            return
        
        # Validate arguments
        if args.min_delay > args.max_delay:
            logger.error("Minimum delay cannot be greater than maximum delay")
            sys.exit(1)
        
        # Run batch commenting
        results = poster.post_comments_batch(
            max_comments=args.max_comments,
            delay_range=(args.min_delay, args.max_delay)
        )
        
        # Display results
        print(f"\n{'='*60}")
        print("COMMENTING RESULTS")
        print(f"{'='*60}")
        print(f"Comments posted: {results['comments_posted']}")
        print(f"Profiles advanced to week3_invitation: {results['profiles_advanced']}")
        
        if results.get('errors'):
            print(f"Errors encountered: {len(results['errors'])}")
            for error in results['errors'][:3]:  # Show first 3 errors
                print(f"  - {error}")
        
        if results['comments_posted'] > 0:
            print("✅ Commenting completed successfully!")
        elif results.get('message'):
            print(f"ℹ️ {results['message']}")
        else:
            print("⚠️ No comments were successfully posted")
        
    except Exception as e:
        logger.error(f"Comment poster failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
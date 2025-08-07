#!/usr/bin/env python3
"""
Post Liker - Standalone Script
Purpose: Like LinkedIn posts for profiles in week1_liking status and advance them to week2_commenting
Usage: 
    python post_liker.py [--max-likes=25] [--delay=5]
"""

import os
import sys
import sqlite3
import requests
import json
import re
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
        logging.FileHandler('post_liker.log')
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

class PostLiker:
    def __init__(self, db_path: str = DB_PATH):
        """Initialize the post liker."""
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
                    FOREIGN KEY (profile_id) REFERENCES profiles (profile_id)
                )
            """)
            
            # Add missing columns to existing posts table
            cursor.execute("PRAGMA table_info(posts)")
            existing_columns = {col[1] for col in cursor.fetchall()}
            
            new_columns = [
                ("liked_to_linkedin_at", "TIMESTAMP"),
                ("linkedin_like_id", "TEXT"),
                ("linkedin_like_urn", "TEXT"),
                ("is_post_liked", "BOOLEAN DEFAULT FALSE"),
                ("like_failed", "BOOLEAN DEFAULT FALSE")
            ]
            
            for column_name, column_def in new_columns:
                if column_name not in existing_columns:
                    try:
                        cursor.execute(f"ALTER TABLE posts ADD COLUMN {column_name} {column_def}")
                        logger.info(f"Added column {column_name} to posts table")
                    except sqlite3.OperationalError as e:
                        if "duplicate column" not in str(e).lower():
                            raise
            
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

    def get_posts_to_like(self) -> List[Dict]:
        """Get posts from profiles in week1_liking status with recent posts (max 3 per profile)."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Check if required columns exist
            cursor.execute("PRAGMA table_info(posts)")
            existing_columns = {col[1] for col in cursor.fetchall()}
            
            # Build the query based on available columns
            if 'is_post_liked' in existing_columns:
                liked_condition = "AND (posts.is_post_liked IS NULL OR posts.is_post_liked = FALSE)"
            else:
                liked_condition = ""
            
            query = f"""
                SELECT profiles.profile_id, profiles.first_name, profiles.last_name,
                       profiles.connection_status,
                       posts.post_id, posts.urn, posts.text, posts.posted_date
                FROM profiles
                JOIN posts ON posts.profile_id = profiles.profile_id
                WHERE profiles.status = 'week1_liking'
                  AND date(substr(posts.posted_date, 1, 10)) > date('now', '-21 days')
                  {liked_condition}
                  AND posts.urn IS NOT NULL
                  AND posts.urn != ''
                ORDER BY profiles.job_title_score DESC, posts.posted_date DESC
            """
            
            logger.debug(f"Executing query: {query}")
            cursor.execute(query)
            
            all_posts = [dict(row) for row in cursor.fetchall()]
            conn.close()
            
            # Apply per-profile rate limiting (max 3 posts per profile)
            if not all_posts:
                logger.info("No posts found that need liking")
                return []
            
            profile_counts = {}
            filtered_posts = []
            
            for post in all_posts:
                profile_id = post['profile_id']
                current_count = profile_counts.get(profile_id, 0)
                
                if current_count < 3:  # Max 3 posts per profile
                    filtered_posts.append(post)
                    profile_counts[profile_id] = current_count + 1
            
            logger.info(f"Found {len(filtered_posts)} posts ready for liking (max 3 per profile)")
            if len(all_posts) != len(filtered_posts):
                profiles_limited = len([p for p in profile_counts.values() if p >= 3])
                logger.info(f"Rate limiting applied: {len(all_posts)} total posts → {len(filtered_posts)} posts "
                           f"({profiles_limited} profiles hit the 3-post limit)")
            
            return filtered_posts
            
        except Exception as e:
            logger.error(f"Error getting posts to like: {e}")
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

    def format_post_urn(self, post_urn_or_id: str) -> str:
        """Convert numeric post ID to proper LinkedIn URN format if needed."""
        if post_urn_or_id.startswith('urn:li:'):
            return post_urn_or_id
        
        # Convert numeric ID to activity URN format (LinkedIn's primary format)
        return f"urn:li:activity:{post_urn_or_id}"
    
    def get_alternative_urn_formats(self, post_urn_or_id: str) -> List[str]:
        """Generate alternative URN formats to try if the primary format fails."""
        if post_urn_or_id.startswith('urn:li:'):
            # Extract numeric ID from existing URN
            numeric_match = re.search(r':(\d+)$', post_urn_or_id)
            if numeric_match:
                numeric_id = numeric_match.group(1)
            else:
                return [post_urn_or_id]  # Return original if can't extract ID
        else:
            numeric_id = post_urn_or_id
        
        # Return different URN formats to try
        return [
            f"urn:li:activity:{numeric_id}",      # Primary format
            f"urn:li:ugcPost:{numeric_id}",       # Alternative format
            f"urn:li:share:{numeric_id}"          # Another possible format
        ]

    def create_linkedin_like_payload(self, post_urn: str, user_id: str) -> Dict:
        """Create the JSON payload for LinkedIn like API."""
        return {
            "actor": f"urn:li:person:{user_id}",
            "object": post_urn
        }

    def get_like_endpoint_url(self, post_urn: str) -> str:
        """Generate the like endpoint URL for a specific post."""
        import urllib.parse
        encoded_urn = urllib.parse.quote(post_urn, safe='')
        return f"https://api.linkedin.com/v2/socialActions/{encoded_urn}/likes"

    def like_post_on_linkedin(self, post_urn: str, user_id: str) -> Optional[Dict]:
        """Like post on LinkedIn using v2 API with retry logic for URN mismatches."""
        formatted_urn = self.format_post_urn(post_urn)
        
        try:
            logger.info(f"Attempting to like post: {formatted_urn}")
            
            payload = self.create_linkedin_like_payload(formatted_urn, user_id)
            headers = self.get_headers()
            endpoint_url = self.get_like_endpoint_url(formatted_urn)
            
            response = self.session.post(endpoint_url, headers=headers, json=payload, timeout=30)
            
            if response.status_code in [200, 201]:
                response_data = response.json() if response.content else {}
                like_id = (response.headers.get('x-linkedin-id') or
                          response.headers.get('x-restli-id') or
                          response.headers.get('location', '').split('/')[-1] or
                          response_data.get('id', 'unknown'))
                
                logger.info(f"Successfully liked post. Like ID: {like_id}")
                return {
                    'success': True,
                    'like_id': like_id,
                    'response_data': response_data
                }
            elif response.status_code == 409:
                # Post already liked - treat as success
                logger.info(f"Post already liked (409 conflict): {formatted_urn}")
                return {
                    'success': True,
                    'like_id': 'already_liked',
                    'response_data': {'status': 'already_liked'}
                }
            else:
                raise requests.exceptions.HTTPError(response=response)

        except requests.exceptions.HTTPError as e:
            error_text = e.response.text
            
            # Handle URN mismatch with retry logic
            if e.response.status_code == 400 and "is not the same as the actual threadUrn" in error_text:
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
                
                for pattern in patterns:
                    match = re.search(pattern, error_text)
                    if match:
                        correct_urn = match.group(1)
                        logger.info(f"Found correct URN using pattern '{pattern}': {correct_urn}")
                        break
                
                if correct_urn:
                    try:
                        # Retry with correct URN
                        retry_payload = self.create_linkedin_like_payload(correct_urn, user_id)
                        retry_endpoint_url = self.get_like_endpoint_url(correct_urn)
                        
                        retry_response = self.session.post(
                            retry_endpoint_url, 
                            headers=headers, 
                            json=retry_payload, 
                            timeout=30
                        )
                        
                        if retry_response.status_code in [200, 201]:
                            retry_data = retry_response.json() if retry_response.content else {}
                            retry_like_id = (retry_response.headers.get('x-linkedin-id') or
                                           retry_response.headers.get('x-restli-id') or
                                           'unknown')
                            
                            logger.info(f"Retry successful. Like ID: {retry_like_id}")
                            return {
                                'success': True,
                                'like_id': retry_like_id,
                                'response_data': retry_data
                            }
                        elif retry_response.status_code == 409:
                            # Post already liked on retry - treat as success
                            logger.info(f"Post already liked on retry (409 conflict): {correct_urn}")
                            return {
                                'success': True,
                                'like_id': 'already_liked',
                                'response_data': {'status': 'already_liked'}
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
                logger.error(f"LinkedIn API error: {e.response.status_code} - {error_text}")
                return None
        
        except Exception as e:
            logger.error(f"Unexpected error liking post {formatted_urn}: {e}")
            return None

    def mark_post_as_liked(self, post_id: int, linkedin_like_id: str, linkedin_like_urn: str) -> bool:
        """Mark post as successfully liked in the database."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Check what columns exist
            cursor.execute("PRAGMA table_info(posts)")
            existing_columns = {col[1] for col in cursor.fetchall()}
            
            # Build update query based on available columns
            update_parts = []
            params = []
            
            if 'is_post_liked' in existing_columns:
                update_parts.append("is_post_liked = TRUE")
            
            if 'liked_to_linkedin_at' in existing_columns:
                update_parts.append("liked_to_linkedin_at = CURRENT_TIMESTAMP")
            
            if 'linkedin_like_id' in existing_columns:
                update_parts.append("linkedin_like_id = ?")
                params.append(linkedin_like_id)
            
            if 'linkedin_like_urn' in existing_columns:
                update_parts.append("linkedin_like_urn = ?")
                params.append(linkedin_like_urn)
            
            if not update_parts:
                logger.warning("No appropriate columns found to mark post as liked")
                conn.close()
                return False
            
            params.append(post_id)
            
            update_sql = f"""
                UPDATE posts
                SET {', '.join(update_parts)}
                WHERE post_id = ?
            """
            
            cursor.execute(update_sql, params)
            
            updated = cursor.rowcount > 0
            conn.commit()
            conn.close()
            
            if updated:
                logger.info(f"Marked post {post_id} as liked")
            else:
                logger.warning(f"Failed to mark post {post_id} as liked")
            
            return updated
            
        except sqlite3.Error as e:
            logger.error(f"Error marking post {post_id} as liked: {e}")
            return False

    def mark_post_like_failed(self, post_id: int, error_message: str) -> bool:
        """Mark post as failed to like."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Check if like_failed column exists
            cursor.execute("PRAGMA table_info(posts)")
            existing_columns = {col[1] for col in cursor.fetchall()}
            
            if 'like_failed' in existing_columns:
                cursor.execute("""
                    UPDATE posts
                    SET like_failed = TRUE
                    WHERE post_id = ?
                """, (post_id,))
                
                updated = cursor.rowcount > 0
                conn.commit()
                
                if updated:
                    logger.info(f"Marked post {post_id} as failed to like: {error_message}")
            else:
                logger.info(f"Post {post_id} failed to like (no tracking column): {error_message}")
                updated = True  # Consider it successful since we logged it
            
            conn.close()
            return updated
            
        except sqlite3.Error as e:
            logger.error(f"Error marking post {post_id} as failed: {e}")
            return False

    def get_failure_status_for_connection_type(self, connection_status: str) -> str:
        """Determine the correct failure status based on connection type."""
        if connection_status == 'prospect':
            return 'week3_invitation'  # Prospects that fail liking go to invitations
        elif connection_status == 'current_connection':
            return 'maintenance'  # Current connections that fail go back to maintenance
        else:
            # Default fallback
            logger.warning(f"Unknown connection_status: {connection_status}, defaulting to week3_invitation")
            return 'week3_invitation'

    def update_profile_status(self, profile_id: int, new_status: str, reason: str = "") -> bool:
        """Update profile status after successful like."""
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

    def like_post(self, post_data: Dict, user_id: str) -> Dict:
        """Like a single post and return results."""
        post_id = post_data['post_id']
        profile_id = post_data['profile_id']
        name = f"{post_data['first_name']} {post_data['last_name']}"
        post_urn = post_data['urn']
        
        result = {
            'post_id': post_id,
            'profile_id': profile_id,
            'name': name,
            'success': False,
            'profile_updated': False
        }
        
        try:
            logger.info(f"Liking post {post_id} by {name}")
            
            # Attempt to like the post
            like_response = self.like_post_on_linkedin(post_urn, user_id)
            
            if like_response and like_response.get('success'):
                # Mark post as liked
                post_marked = self.mark_post_as_liked(
                    post_id,
                    like_response.get('like_id', 'unknown'),
                    like_response.get('response_data', {}).get('id', 'unknown')
                )
                
                if post_marked:
                    # Update profile status to week2_commenting
                    profile_updated = self.update_profile_status(
                        profile_id, 
                        'week2_commenting', 
                        f"Liked post {post_id}"
                    )
                    
                    result['success'] = True
                    result['profile_updated'] = profile_updated
                    logger.info(f"✅ Successfully liked post {post_id} by {name}")
                else:
                    logger.error(f"Failed to mark post {post_id} as liked in database")
            else:
                # Mark post as failed
                self.mark_post_like_failed(post_id, "LinkedIn API error")
                
                # Update profile status based on connection type
                connection_status = post_data.get('connection_status', 'prospect')
                failure_status = self.get_failure_status_for_connection_type(connection_status)
                
                profile_updated = self.update_profile_status(
                    profile_id, 
                    failure_status, 
                    f"Failed to like post {post_id} - moved to {failure_status}"
                )
                
                result['failure_status'] = failure_status
                result['profile_updated'] = profile_updated
                logger.error(f"❌ Failed to like post {post_id} by {name} - moved profile to {failure_status}")
                
        except Exception as e:
            logger.error(f"❌ Error liking post {post_id}: {e}")
            result['error'] = str(e)
        
        return result

    def like_posts_batch(self, max_likes: int = 25, delay_range: Tuple[int, int] = (5, 25)) -> Dict:
        """Like a batch of posts with human-like delays."""
        logger.info(f"Starting post liking batch (max {max_likes} likes)")
        
        # Validate credentials
        validation_result = self.validate_linkedin_credentials()
        if not validation_result.get('valid', False):
            logger.error("LinkedIn credentials validation failed")
            return {
                'success': False, 
                'error': validation_result.get('error', 'Invalid credentials'),
                'likes_completed': 0,
                'profiles_advanced': 0
            }
        
        user_id = validation_result.get('user_id')
        if not user_id:
            logger.error("Failed to get user ID from LinkedIn validation")
            return {
                'success': False, 
                'error': 'No user ID',
                'likes_completed': 0,
                'profiles_advanced': 0
            }
        
        # Get posts to like
        posts_to_like = self.get_posts_to_like()
        
        if not posts_to_like:
            logger.info("No posts found that need liking")
            return {
                'success': True,
                'likes_completed': 0,
                'profiles_advanced': 0,
                'message': 'No posts to like'
            }
        
        # Limit to max_likes
        posts_to_process = posts_to_like[:max_likes]
        logger.info(f"Processing {len(posts_to_process)} posts")
        
        batch_results = {
            'success': True,
            'likes_completed': 0,
            'profiles_advanced': 0,
            'errors': [],
            'results': []
        }
        
        for i, post_data in enumerate(posts_to_process):
            logger.info(f"Processing post {i+1}/{len(posts_to_process)}")
            
            # Like the post
            result = self.like_post(post_data, user_id)
            batch_results['results'].append(result)
            
            if result['success']:
                batch_results['likes_completed'] += 1
                if result['profile_updated']:
                    batch_results['profiles_advanced'] += 1
            else:
                if 'error' in result:
                    batch_results['errors'].append(result['error'])
            
            # Apply human-like delay between likes (except after the last one)
            if i < len(posts_to_process) - 1:
                delay = random.randint(delay_range[0], delay_range[1])
                logger.info(f"Human-like delay: {delay}s...")
                time.sleep(delay)
        
        logger.info(f"Batch liking completed: {batch_results['likes_completed']} likes, {batch_results['profiles_advanced']} profiles advanced")
        return batch_results

    def debug_post_query(self) -> None:
        """Debug method to show detailed information about posts and profiles."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            logger.info("=== POST QUERY DEBUG ===")
            
            # Show all profiles and their statuses
            cursor.execute("SELECT profile_id, first_name, last_name, status FROM profiles LIMIT 10")
            profiles = cursor.fetchall()
            logger.info("Sample profiles:")
            for profile in profiles:
                logger.info(f"  ID {profile['profile_id']}: {profile['first_name']} {profile['last_name']} - {profile['status']}")
            
            # Show posts with their details
            cursor.execute("""
                SELECT p.profile_id, p.first_name, p.last_name, p.status,
                       po.post_id, po.urn, po.posted_date, po.is_post_liked
                FROM profiles p
                LEFT JOIN posts po ON p.profile_id = po.profile_id
                WHERE p.status = 'week1_liking'
                LIMIT 5
            """)
            week1_details = cursor.fetchall()
            logger.info("Week1_liking profiles and their posts:")
            for row in week1_details:
                logger.info(f"  Profile {row['profile_id']} ({row['first_name']} {row['last_name']}): Post {row['post_id']}, URN: {row['urn']}, Date: {row['posted_date']}, Liked: {row['is_post_liked']}")
            
            # Check the exact query we use
            cursor.execute("""
                SELECT profiles.profile_id, profiles.first_name, profiles.last_name,
                       posts.post_id, posts.urn, posts.posted_date,
                       date(posts.posted_date) as parsed_date,
                       date(substr(posts.posted_date, 1, 10)) as substr_date,
                       date('now', '-21 days') as threshold_date,
                       (date(posts.posted_date) > date('now', '-21 days')) as is_recent_original,
                       (date(substr(posts.posted_date, 1, 10)) > date('now', '-21 days')) as is_recent_substr,
                       julianday('now') - julianday(substr(posts.posted_date, 1, 10)) as days_ago
                FROM profiles
                JOIN posts ON posts.profile_id = profiles.profile_id
                WHERE profiles.status = 'week1_liking'
                  AND posts.urn IS NOT NULL
                  AND posts.urn != ''
                LIMIT 5
            """)
            query_details = cursor.fetchall()
            logger.info("Query breakdown (before date filter):")
            for row in query_details:
                logger.info(f"  Profile {row['profile_id']}: Post {row['post_id']}, Date: {row['posted_date']}, Parsed: {row['parsed_date']}, Threshold: {row['threshold_date']}, Recent: {row['is_recent']}")
            
            conn.close()
            
        except Exception as e:
            logger.error(f"Error in debug query: {e}")

    def get_liking_stats(self) -> Dict:
        """Get current liking statistics."""
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
            
            # Posts stats
            cursor.execute("SELECT COUNT(*) as count FROM posts WHERE urn IS NOT NULL AND urn != ''")
            stats['total_posts_with_urn'] = cursor.fetchone()['count']
            
            # Check if columns exist before querying them
            cursor.execute("PRAGMA table_info(posts)")
            existing_columns = {col[1] for col in cursor.fetchall()}
            
            if 'is_post_liked' in existing_columns:
                cursor.execute("SELECT COUNT(*) as count FROM posts WHERE is_post_liked = TRUE")
                stats['liked_posts'] = cursor.fetchone()['count']
            else:
                stats['liked_posts'] = 0
            
            if 'like_failed' in existing_columns:
                cursor.execute("SELECT COUNT(*) as count FROM posts WHERE like_failed = TRUE")
                stats['failed_likes'] = cursor.fetchone()['count']
            else:
                stats['failed_likes'] = 0
            
            # Week1 liking candidates with debug info
            cursor.execute("""
                SELECT COUNT(DISTINCT profiles.profile_id) as count
                FROM profiles
                JOIN posts ON posts.profile_id = profiles.profile_id
                WHERE profiles.status = 'week1_liking'
                  AND date(substr(posts.posted_date, 1, 10)) > date('now', '-21 days')
                  AND (posts.is_post_liked IS NULL OR posts.is_post_liked = FALSE)
                  AND posts.urn IS NOT NULL
                  AND posts.urn != ''
            """)
            stats['week1_candidates'] = cursor.fetchone()['count']
            
            # Debug: Check what profiles are in week1_liking
            cursor.execute("SELECT COUNT(*) as count FROM profiles WHERE status = 'week1_liking'")
            stats['debug_week1_profiles'] = cursor.fetchone()['count']
            
            # Debug: Check posts with recent dates
            cursor.execute("""
                SELECT COUNT(*) as count FROM posts 
                WHERE date(substr(posts.posted_date, 1, 10)) > date('now', '-21 days')
                AND urn IS NOT NULL AND urn != ''
            """)
            stats['debug_recent_posts'] = cursor.fetchone()['count']
            
            # Last liked date
            if 'liked_to_linkedin_at' in existing_columns:
                cursor.execute("""
                    SELECT liked_to_linkedin_at 
                    FROM posts 
                    WHERE is_post_liked = TRUE 
                    ORDER BY liked_to_linkedin_at DESC 
                    LIMIT 1
                """)
                result = cursor.fetchone()
                stats['last_liked'] = result['liked_to_linkedin_at'] if result else None
            else:
                stats['last_liked'] = None
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"Error getting liking stats: {e}")
            return {}

def main():
    """Main function."""
    parser = argparse.ArgumentParser(description="LinkedIn Post Liker")
    parser.add_argument('--max-likes', type=int, default=25,
                       help='Maximum number of posts to like (default: 25)')
    parser.add_argument('--min-delay', type=int, default=5,
                       help='Minimum delay between likes in seconds (default: 5)')
    parser.add_argument('--max-delay', type=int, default=25,
                       help='Maximum delay between likes in seconds (default: 25)')
    parser.add_argument('--stats-only', action='store_true',
                       help='Show statistics only, do not like posts')
    parser.add_argument('--debug', action='store_true',
                       help='Show detailed debug information about posts and profiles')
    
    args = parser.parse_args()
    
    try:
        # Initialize liker
        liker = PostLiker()
        
        # Show current stats
        logger.info("Current liking statistics:")
        stats = liker.get_liking_stats()
        
        if stats.get('status_breakdown'):
            logger.info("Profile status breakdown:")
            for status, count in stats['status_breakdown'].items():
                logger.info(f"  {status}: {count}")
        
        logger.info(f"Total posts with URN: {stats.get('total_posts_with_urn', 0)}")
        logger.info(f"Posts already liked: {stats.get('liked_posts', 0)}")
        logger.info(f"Failed likes: {stats.get('failed_likes', 0)}")
        logger.info(f"Week1 candidates ready for liking: {stats.get('week1_candidates', 0)}")
        
        # Debug information
        logger.info(f"DEBUG - Profiles in week1_liking status: {stats.get('debug_week1_profiles', 0)}")
        logger.info(f"DEBUG - Posts with recent dates (<21 days): {stats.get('debug_recent_posts', 0)}")
        
        if stats.get('last_liked'):
            logger.info(f"Last liked: {stats['last_liked']}")
        
        if args.debug:
            liker.debug_post_query()
        
        if args.stats_only:
            return
        
        # Validate arguments
        if args.min_delay > args.max_delay:
            logger.error("Minimum delay cannot be greater than maximum delay")
            sys.exit(1)
        
        # Run batch liking
        results = liker.like_posts_batch(
            max_likes=args.max_likes,
            delay_range=(args.min_delay, args.max_delay)
        )
        
        # Display results
        print(f"\n{'='*60}")
        print("LIKING RESULTS")
        print(f"{'='*60}")
        print(f"Posts liked: {results['likes_completed']}")
        print(f"Profiles advanced to week2_commenting: {results['profiles_advanced']}")
        
        if results.get('errors'):
            print(f"Errors encountered: {len(results['errors'])}")
            for error in results['errors'][:3]:  # Show first 3 errors
                print(f"  - {error}")
        
        if results['likes_completed'] > 0:
            print("✅ Liking completed successfully!")
        elif results.get('message'):
            print(f"ℹ️ {results['message']}")
        else:
            print("⚠️ No posts were successfully liked")
            print("💡 Try running with --debug to see what posts are available")
        
    except Exception as e:
        logger.error(f"Post liker failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
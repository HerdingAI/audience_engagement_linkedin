# backend/linkedin/services/sqlite_service.py
import sqlite3
import logging
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class LinkedInSQLiteService:
    def __init__(self, db_path: str = "linkedin_project_db.sqlite3"):
        self.db_path = Path(db_path)
        self._ensure_database_exists()
        self._create_comments_table()
    
    def _ensure_database_exists(self):
        """Ensure the database file exists and has the posts table"""
        if not self.db_path.exists():
            logger.warning(f"Database {self.db_path} does not exist. Creating new database.")
            
        # Create connection to ensure file exists
        with sqlite3.connect(self.db_path) as conn:
            # Verify posts table exists
            cursor = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='posts'
            """)
            if not cursor.fetchone():
                logger.error("Posts table does not exist in database")
                raise Exception("Posts table not found in linkedin_project_db")
    
    def _create_comments_table(self):
        """Create comments table if it doesn't exist"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS comments (
                    comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_id INTEGER NOT NULL,
                    urn TEXT NOT NULL,
                    generated_comment TEXT NOT NULL,
                    research_summary TEXT,
                    is_processed BOOLEAN NOT NULL DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'GENERATED',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (post_id) REFERENCES posts(post_id) ON UPDATE CASCADE ON DELETE CASCADE,
                    UNIQUE(post_id, urn)
                )
            """)
            conn.commit()
            logger.info("Comments table created/verified")
    
    def get_unprocessed_post(self) -> Optional[Dict[str, Any]]:
        """Get one unprocessed post from the database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute("""
                SELECT p.post_id, p.urn, p.text, pr.profile_id, pr.connection_status
                FROM posts p
                JOIN profiles pr ON p.profile_id = pr.profile_id
                LEFT JOIN comments c ON p.post_id = c.post_id 
                WHERE pr.status = 'week2_commenting'
                AND p.text != ''
                AND p.posted_date > datetime('now', '-30 days')
                AND c.post_id IS NULL 
                AND p.reposted = 0
                ORDER BY p.posted_date DESC
                LIMIT 1;

                """)
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            logger.error(f"Database error getting unprocessed post: {e}")
            return None
    
    def save_comment(
        self, 
        post_id: int, 
        urn: str, 
        comment: str, 
        research_summary: str = None,
        status: str = 'GENERATED'
    ) -> int:
        """Save generated comment to database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Check if comment already exists
                cursor = conn.execute("""
                    SELECT comment_id FROM comments WHERE post_id = ? AND urn = ?
                """, (post_id, urn))
                
                if cursor.fetchone():
                    # Update existing comment
                    cursor = conn.execute("""
                        UPDATE comments 
                        SET generated_comment = ?, research_summary = ?, 
                            is_processed = 1, status = ?, created_at = CURRENT_TIMESTAMP
                        WHERE post_id = ? AND urn = ?
                    """, (comment, research_summary, status, post_id, urn))
                else:
                    # Insert new comment
                    cursor = conn.execute("""
                        INSERT INTO comments 
                        (post_id, urn, generated_comment, research_summary, is_processed, status)
                        VALUES (?, ?, ?, ?, 1, ?)
                    """, (post_id, urn, comment, research_summary, status))
                
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error as e:
            logger.error(f"Database error saving comment: {e}")
            raise
    
    def mark_post_discarded(self, post_id: int, urn: str, reason: str = 'DISCARDED_BY_GATEKEEPER'):
        """Mark post as discarded by gatekeeper"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO comments 
                    (post_id, urn, generated_comment, is_processed, status)
                    VALUES (?, ?, '', 1, ?)
                """, (post_id, urn, reason))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error marking post discarded: {e}")
            raise
    
    def mark_comment_rejected(self, post_id: int, urn: str, comment: str, reason: str = 'REJECTED_BY_QC'):
        """Mark comment as rejected by quality check"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO comments 
                    (post_id, urn, generated_comment, is_processed, status)
                    VALUES (?, ?, ?, 1, ?)
                """, (post_id, urn, comment, reason))
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error marking comment rejected: {e}")
            raise
    
    def get_failure_status_for_connection_type(self, connection_status: str) -> str:
        """Determine the correct failure status based on connection type."""
        if connection_status == 'prospect':
            return 'week3_invitation'  # Prospects that fail comment generation go to invitations
        elif connection_status == 'current_connection':
            return 'maintenance'  # Current connections that fail go back to maintenance
        else:
            # Default fallback
            logger.warning(f"Unknown connection_status: {connection_status}, defaulting to week3_invitation")
            return 'week3_invitation'

    def update_profile_status_on_failure(self, profile_id: int, connection_status: str, reason: str = "") -> bool:
        """Update profile status when comment generation fails."""
        try:
            failure_status = self.get_failure_status_for_connection_type(connection_status)
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    UPDATE profiles 
                    SET status = ?, last_action_date = date('now')
                    WHERE profile_id = ?
                """, (failure_status, profile_id))
                
                updated = cursor.rowcount > 0
                conn.commit()
                
                if updated:
                    logger.info(f"Updated profile {profile_id} to status '{failure_status}' due to comment generation failure. {reason}")
                else:
                    logger.warning(f"Failed to update profile {profile_id} status")
                
                return updated
                
        except sqlite3.Error as e:
            logger.error(f"Database error updating profile {profile_id} status: {e}")
            return False

    def get_comment_by_post_id(self, post_id: int) -> Optional[Dict[str, Any]]:
        """Get comment for a specific post"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM comments WHERE post_id = ?
            """, (post_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def get_processing_stats(self) -> Dict[str, int]:
        """Get processing statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                stats = {}
                
                # Total posts
                cursor = conn.execute("SELECT COUNT(*) FROM posts")
                stats['total_posts'] = cursor.fetchone()[0]
                
                # Processed posts
                cursor = conn.execute("SELECT COUNT(*) FROM comments WHERE is_processed = 1")
                stats['processed_posts'] = cursor.fetchone()[0]
                
                # Comments generated
                cursor = conn.execute("SELECT COUNT(*) FROM comments WHERE status = 'GENERATED'")
                stats['comments_generated'] = cursor.fetchone()[0]
                
                # Posts discarded
                cursor = conn.execute("SELECT COUNT(*) FROM comments WHERE status LIKE '%DISCARDED%'")
                stats['posts_discarded'] = cursor.fetchone()[0]
                
                # Comments rejected
                cursor = conn.execute("SELECT COUNT(*) FROM comments WHERE status LIKE '%REJECTED%'")
                stats['comments_rejected'] = cursor.fetchone()[0]
                
                return stats
        except sqlite3.Error as e:
            logger.error(f"Database error getting stats: {e}")
            return {
                'total_posts': 0,
                'processed_posts': 0,
                'comments_generated': 0,
                'posts_discarded': 0,
                'comments_rejected': 0
            }
    
    def cleanup_profiles_without_comments(self) -> int:
        """Move profiles in week2_commenting with no generated comments to week3_invitation"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                # Find profiles in week2_commenting that have no generated comments
                cursor = conn.execute("""
                    SELECT DISTINCT p.profile_id, p.first_name, p.last_name, p.connection_status
                    FROM profiles p
                    WHERE p.status = 'week2_commenting'
                    AND p.profile_id NOT IN (
                        SELECT DISTINCT po.profile_id 
                        FROM posts po 
                        JOIN comments c ON po.post_id = c.post_id 
                        WHERE c.status = 'GENERATED'
                    )
                """)
                
                profiles_to_update = cursor.fetchall()
                
                if not profiles_to_update:
                    logger.info("No profiles need cleanup - all week2_commenting profiles have generated comments")
                    return 0
                
                # Update these profiles to week3_invitation status
                updated_count = 0
                for profile in profiles_to_update:
                    profile_id, first_name, last_name, connection_status = profile
                    
                    # Determine appropriate next status based on connection type
                    if connection_status == 'prospect':
                        next_status = 'week3_invitation'
                    elif connection_status == 'current_connection':
                        next_status = 'maintenance'
                    else:
                        next_status = 'week3_invitation'  # Default fallback
                    
                    cursor = conn.execute("""
                        UPDATE profiles 
                        SET status = ?, last_action_date = date('now')
                        WHERE profile_id = ?
                    """, (next_status, profile_id))
                    
                    if cursor.rowcount > 0:
                        updated_count += 1
                        logger.info(f"Moved profile {profile_id} ({first_name} {last_name}) from week2_commenting to {next_status} - no comments generated")
                
                conn.commit()
                logger.info(f"Cleanup completed: moved {updated_count} profiles from week2_commenting to appropriate next status")
                return updated_count
                
        except sqlite3.Error as e:
            logger.error(f"Database error during profile cleanup: {e}")
            return 0
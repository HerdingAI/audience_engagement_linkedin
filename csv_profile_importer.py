#!/usr/bin/env python3
"""
CSV Profile Importer - Standalone Script
Purpose: Import LinkedIn profiles from CSV with duplicate prevention and connection reconciliation
Usage: 
    python csv_profile_importer.py prospects.csv prospect
    python csv_profile_importer.py connections.csv connection
"""

import os
import sys
import sqlite3
import pandas as pd
import logging
from datetime import datetime
from typing import Dict, Optional
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('csv_importer.log')
    ]
)
logger = logging.getLogger(__name__)

# Database configuration
DB_PATH = "linkedin_project_db.sqlite3"

class CSVProfileImporter:
    def __init__(self, db_path: str = DB_PATH):
        """Initialize the CSV profile importer."""
        self.db_path = db_path
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

    def extract_username_from_url(self, profile_url: str) -> str:
        """Extract username from LinkedIn profile URL."""
        if pd.isna(profile_url) or not profile_url:
            return ''
        
        try:
            if '/in/' in profile_url:
                username = profile_url.split('/in/')[-1].rstrip('/')
                # Remove query parameters
                username = username.split('?')[0].split('#')[0]
                return username
            return ''
        except Exception:
            return ''

    def calculate_job_title_score(self, title: str) -> int:
        """
        Calculate priority score based on job title to find a Product Manager role.
        Explicitly de-prioritizes non-relevant roles.
        """
        if not title or pd.isna(title):
            return 1
            
        title_lower = str(title).lower()
        
        # Tier 1: Product Leadership & Recruiters (Highest Priority)
        if any(word in title_lower for word in ['chief product officer', 'cpo', 'vp of product', 'head of product', 'director of product', 'product recruiter']):
            return 10
            
        # Tier 2: Senior Product Managers
        elif any(word in title_lower for word in ['senior product manager', 'principal product manager', 'lead product manager']):
            return 8
            
        # Tier 3: Product Managers
        elif 'product manager' in title_lower or 'pm' in title_lower:
            return 6
            
        # Tier 4: Adjacent & Junior Product Roles
        elif any(word in title_lower for word in ['associate product manager', 'apm', 'product owner', 'product marketing']):
            return 4
            
        # Tier 5: General Tech Leadership
        elif any(word in title_lower for word in ['cto', 'vp of engineering', 'director of engineering', 'recruiter', 'talent acquisition']):
            return 2
            
        # Tier 6: Non-Relevant Roles (Explicitly de-prioritized)
        elif any(word in title_lower for word in [
            'sales', 'account executive', 'marketing', 'finance', 'accountant', 
            'human resources', 'customer success', 'operations', 'legal', 'counsel'
        ]):
            return 1
            
        # Default catch-all for any other title
        else:
            return 1

    def validate_csv_format(self, df: pd.DataFrame) -> bool:
        """Validate that CSV has required columns."""
        required_cols = ['first_name', 'last_name', 'profile_url']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            logger.error(f"Missing required columns: {missing_cols}")
            return False
        
        return True

    def clean_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Clean dataframe by removing completely empty rows and rows with missing critical data."""
        original_count = len(df)
        
        # Remove completely empty rows (all values are NaN)
        df_cleaned = df.dropna(how='all')
        completely_empty = original_count - len(df_cleaned)
        
        if completely_empty > 0:
            logger.info(f"Removed {completely_empty} completely empty rows")
        
        # Remove rows missing critical fields (first_name, last_name, profile_url)
        critical_fields = ['first_name', 'last_name', 'profile_url']
        df_cleaned = df_cleaned.dropna(subset=critical_fields)
        
        missing_critical = len(df) - len(df_cleaned) - completely_empty
        if missing_critical > 0:
            logger.warning(f"Removed {missing_critical} rows missing critical fields (first_name, last_name, or profile_url)")
        
        logger.info(f"Cleaned dataset: {original_count} → {len(df_cleaned)} rows ({original_count - len(df_cleaned)} removed)")
        return df_cleaned

    def import_prospects(self, csv_file_path: str) -> Dict:
        """Import new prospects from CSV."""
        try:
            # Read and validate CSV
            df = pd.read_csv(csv_file_path)
            logger.info(f"Read {len(df)} rows from CSV")
            
            if not self.validate_csv_format(df):
                raise ValueError("CSV format validation failed")
            
            # Clean the dataframe
            df = self.clean_dataframe(df)
            
            if len(df) == 0:
                logger.error("No valid rows remaining after cleaning")
                return {
                    'total_rows': 0,
                    'new_profiles': 0,
                    'duplicates_skipped': 0,
                    'errors': 0
                }
            
            # Extract username if missing
            if 'username' not in df.columns:
                df['username'] = df['profile_url'].apply(self.extract_username_from_url)
                logger.info("Extracted usernames from profile_url column")
            
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            results = {
                'total_rows': len(df),
                'new_profiles': 0,
                'duplicates_skipped': 0,
                'errors': 0
            }
            
            # Get existing profiles to check duplicates
            cursor.execute("SELECT profile_url, username FROM profiles")
            existing_profiles = {(row['profile_url'], row['username']) for row in cursor.fetchall()}
            
            for _, row in df.iterrows():
                try:
                    profile_key = (row['profile_url'], row['username'])
                    
                    # Check if profile already exists
                    if profile_key in existing_profiles:
                        results['duplicates_skipped'] += 1
                        logger.debug(f"Skipping duplicate: {row['first_name']} {row['last_name']}")
                        continue
                    
                    # Calculate job title score
                    job_title = row.get('job_title', '')
                    job_title_score = self.calculate_job_title_score(job_title)
                    
                    # Insert new prospect
                    cursor.execute("""
                        INSERT INTO profiles (
                            first_name, last_name, username, profile_url, 
                            company_name, job_title, status, connection_status,
                            job_title_score, priority_score, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        row['first_name'], 
                        row['last_name'], 
                        row['username'], 
                        row['profile_url'], 
                        row.get('company_name', ''),
                        job_title,
                        'not_started',
                        'prospect',
                        job_title_score, 
                        job_title_score,
                        datetime.now()
                    ))
                    
                    results['new_profiles'] += 1
                    
                except Exception as e:
                    logger.error(f"Error importing row: {e}")
                    results['errors'] += 1
            
            conn.commit()
            conn.close()
            
            logger.info(f"Prospect import completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Prospect import failed: {e}")
            raise

    def import_connections(self, csv_file_path: str) -> Dict:
        """Import current connections and reconcile with existing prospects."""
        try:
            # Read and validate CSV
            df = pd.read_csv(csv_file_path)
            logger.info(f"Read {len(df)} connection rows from CSV")
            
            if not self.validate_csv_format(df):
                raise ValueError("CSV format validation failed")
            
            # Clean the dataframe
            df = self.clean_dataframe(df)
            
            if len(df) == 0:
                logger.error("No valid rows remaining after cleaning")
                return {
                    'total_rows': 0,
                    'new_connections': 0,
                    'reconciled_prospects': 0,
                    'duplicates_skipped': 0,
                    'errors': 0
                }
            
            # Extract username if missing
            if 'username' not in df.columns:
                df['username'] = df['profile_url'].apply(self.extract_username_from_url)
            
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            results = {
                'total_rows': len(df),
                'new_connections': 0,
                'reconciled_prospects': 0,
                'duplicates_skipped': 0,
                'errors': 0
            }
            
            for _, row in df.iterrows():
                try:
                    profile_url = row['profile_url']
                    
                    # Check if profile already exists (match by URL regardless of status)
                    cursor.execute("""
                        SELECT profile_id, status, connection_status, first_name, last_name 
                        FROM profiles 
                        WHERE profile_url = ?
                    """, (profile_url,))
                    
                    existing_profile = cursor.fetchone()
                    
                    if existing_profile:
                        # Only update if not already a connection
                        if existing_profile['connection_status'] != 'current_connection':
                            # Reconcile existing prospect to connection
                            cursor.execute("""
                                UPDATE profiles 
                                SET status = 'maintenance',
                                    connection_status = 'current_connection',
                                    last_action_date = date('now')
                                WHERE profile_id = ?
                            """, (existing_profile['profile_id'],))
                            
                            results['reconciled_prospects'] += 1
                            logger.info(f"Reconciled prospect to connection: {existing_profile['first_name']} {existing_profile['last_name']} (was {existing_profile['status']})")
                        else:
                            results['duplicates_skipped'] += 1
                            logger.debug(f"Skipping existing connection: {existing_profile['first_name']} {existing_profile['last_name']}")
                    else:
                        # Insert new connection
                        job_title = row.get('job_title', '')
                        job_title_score = self.calculate_job_title_score(job_title)
                        
                        cursor.execute("""
                            INSERT INTO profiles (
                                first_name, last_name, username, profile_url, 
                                company_name, job_title, status, connection_status,
                                job_title_score, priority_score, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            row['first_name'], 
                            row['last_name'], 
                            row.get('username', ''), 
                            profile_url, 
                            row.get('company_name', ''),
                            job_title,
                            'maintenance',
                            'current_connection',
                            job_title_score, 
                            job_title_score,
                            datetime.now()
                        ))
                        
                        results['new_connections'] += 1
                        logger.info(f"Added new connection: {row['first_name']} {row['last_name']}")
                    
                except Exception as e:
                    logger.error(f"Error processing connection row: {e}")
                    results['errors'] += 1
            
            conn.commit()
            conn.close()
            
            logger.info(f"Connection import completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Connection import failed: {e}")
            raise

    def get_import_stats(self) -> Dict:
        """Get current database statistics."""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            stats = {}
            
            # Total profiles
            cursor.execute("SELECT COUNT(*) as count FROM profiles")
            stats['total_profiles'] = cursor.fetchone()['count']
            
            # By connection status
            cursor.execute("""
                SELECT connection_status, COUNT(*) as count 
                FROM profiles 
                GROUP BY connection_status
            """)
            for row in cursor.fetchall():
                stats[f"{row['connection_status']}_count"] = row['count']
            
            # By status
            cursor.execute("""
                SELECT status, COUNT(*) as count 
                FROM profiles 
                GROUP BY status
            """)
            status_counts = {}
            for row in cursor.fetchall():
                status_counts[row['status']] = row['count']
            stats['status_breakdown'] = status_counts
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {}

def print_usage():
    """Print usage instructions."""
    print("\nCSV Profile Importer")
    print("===================")
    print("Usage:")
    print("  python csv_profile_importer.py <csv_file> <import_type>")
    print("\nImport Types:")
    print("  prospect    - Import new prospects (status: not_started)")
    print("  connection  - Import current connections (status: maintenance)")
    print("\nRequired CSV Columns:")
    print("  - first_name")
    print("  - last_name") 
    print("  - profile_url")
    print("\nOptional CSV Columns:")
    print("  - username (extracted from profile_url if missing)")
    print("  - company_name")
    print("  - job_title")
    print("\nExamples:")
    print("  python csv_profile_importer.py prospects.csv prospect")
    print("  python csv_profile_importer.py my_connections.csv connection")

def main():
    """Main function."""
    if len(sys.argv) != 3:
        print_usage()
        sys.exit(1)
    
    csv_file = sys.argv[1]
    import_type = sys.argv[2].lower()
    
    # Validate arguments
    if not Path(csv_file).exists():
        logger.error(f"CSV file not found: {csv_file}")
        sys.exit(1)
    
    if import_type not in ['prospect', 'connection']:
        logger.error(f"Invalid import type: {import_type}")
        print_usage()
        sys.exit(1)
    
    try:
        # Initialize importer
        importer = CSVProfileImporter()
        
        # Show current stats
        logger.info("Current database statistics:")
        stats = importer.get_import_stats()
        for key, value in stats.items():
            if key != 'status_breakdown':
                logger.info(f"  {key}: {value}")
        
        if stats.get('status_breakdown'):
            logger.info("  Status breakdown:")
            for status, count in stats['status_breakdown'].items():
                logger.info(f"    {status}: {count}")
        
        # Preview CSV
        df = pd.read_csv(csv_file)
        logger.info(f"\nCSV Preview ({len(df)} rows):")
        logger.info(f"Columns: {list(df.columns)}")
        if not df.empty:
            logger.info("First few rows:")
            print(df.head().to_string())
        
        # Confirm import
        response = input(f"\nProceed with {import_type} import of {len(df)} profiles? (y/n): ")
        if response.lower() != 'y':
            logger.info("Import cancelled by user")
            return
        
        # Execute import
        if import_type == 'prospect':
            results = importer.import_prospects(csv_file)
        else:
            results = importer.import_connections(csv_file)
        
        # Display results
        print(f"\n{'='*50}")
        print("IMPORT RESULTS")
        print(f"{'='*50}")
        for key, value in results.items():
            print(f"{key.replace('_', ' ').title()}: {value}")
        
        # Show updated stats
        updated_stats = importer.get_import_stats()
        print(f"\nUpdated total profiles: {updated_stats.get('total_profiles', 0)}")
        
        if results.get('new_profiles', 0) > 0 or results.get('new_connections', 0) > 0:
            print("✅ Import completed successfully!")
        
    except Exception as e:
        logger.error(f"Import failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
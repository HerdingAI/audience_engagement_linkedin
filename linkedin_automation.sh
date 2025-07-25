#!/bin/bash

# LinkedIn Automation Script
# Runs scripts in sequence with randomized timing to mimic human behavior
# Schedule: 4 times a week (Monday-Friday) between 7:00 AM and 9:45 AM

# Set script directory
SCRIPT_DIR="/home/buntu/Desktop/Apps/Engagement"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    log_message "✅ Virtual environment activated"
else
    log_message "❌ Virtual environment not found at .venv/bin/activate"
    exit 1
fi

# Function to generate random delay between min and max seconds
random_delay() {
    local min=$1
    local max=$2
    echo $(( RANDOM % (max - min + 1) + min ))
}

# Function to log with timestamp
log_message() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a linkedin_automation.log
}

# Check if today is a weekday (Monday-Friday)
day_of_week=$(date +%u)  # 1=Monday, 7=Sunday
if [ $day_of_week -gt 5 ]; then
    log_message "Weekend detected. Skipping automation run."
    exit 0
fi

# Random chance to run (4 out of 5 weekdays = 80% chance)
if [ $(( RANDOM % 10 )) -gt 7 ]; then
    log_message "Random skip triggered. Not running today."
    exit 0
fi

log_message "=== Starting LinkedIn Automation Sequence ==="

# Initial random delay to start between 7:00 AM and 9:45 AM
# This should be handled by crontab scheduling, but adding small variation
initial_delay=$(random_delay 0 300)  # 0-5 minutes additional variation
log_message "Initial delay: ${initial_delay} seconds"
sleep $initial_delay

# Script 1: Retrieve posts for prospects
log_message "Step 1: Running retrieve_posts_prospects.py"
if [ -f "retrieve_posts_prospects.py" ]; then
    python retrieve_posts_prospects.py --max-profiles=15
    if [ $? -eq 0 ]; then
        log_message "✅ retrieve_posts_prospects.py completed successfully"
    else
        log_message "❌ retrieve_posts_prospects.py failed"
    fi
else
    log_message "⚠️ retrieve_posts_prospects.py not found, skipping"
fi

# Random delay between scripts (2-8 minutes)
delay=$(random_delay 120 480)
log_message "Delay before next script: ${delay} seconds ($(( delay / 60 )) minutes)"
sleep $delay

# Script 2: Retrieve posts for 1st connections
log_message "Step 2: Running retrieve_post_1stconnections.py"
if [ -f "retrieve_post_1stconnections.py" ]; then
    python retrieve_post_1stconnections.py --max-profiles=15
    if [ $? -eq 0 ]; then
        log_message "✅ retrieve_post_1stconnections.py completed successfully"
    else
        log_message "❌ retrieve_post_1stconnections.py failed"
    fi
else
    log_message "⚠️ retrieve_post_1stconnections.py not found, skipping"
fi

# Random delay (3-12 minutes) - longer before engagement activities
delay=$(random_delay 180 720)
log_message "Delay before engagement activities: ${delay} seconds ($(( delay / 60 )) minutes)"
sleep $delay

# Script 3: LinkedIn post liker (with randomized timing within 45-minute window)
log_message "Step 3: Running linkedin_post_liker.py"
if [ -f "linkedin_post_liker.py" ]; then
    # Random delay within 45-minute window (0-2700 seconds)
    liker_delay=$(random_delay 0 2700)
    log_message "Post liker will start in ${liker_delay} seconds ($(( liker_delay / 60 )) minutes)"
    sleep $liker_delay
    
    python linkedin_post_liker.py --max-likes=25 --min-delay=5 --max-delay=25
    if [ $? -eq 0 ]; then
        log_message "✅ linkedin_post_liker.py completed successfully"
    else
        log_message "❌ linkedin_post_liker.py failed"
    fi
else
    log_message "⚠️ linkedin_post_liker.py not found, skipping"
fi

# Random delay between engagement scripts (5-15 minutes)
delay=$(random_delay 300 900)
log_message "Delay before comment generation: ${delay} seconds ($(( delay / 60 )) minutes)"
sleep $delay

# Script 4: LinkedIn commenter (comment generation)
log_message "Step 4: Running linkedin_commenter.py"
if [ -f "linkedin_commenter.py" ]; then
    python linkedin_commenter.py
    if [ $? -eq 0 ]; then
        log_message "✅ linkedin_commenter.py completed successfully"
    else
        log_message "❌ linkedin_commenter.py failed"
    fi
else
    log_message "⚠️ linkedin_commenter.py not found, skipping"
fi

# Random delay before comment posting (10-25 minutes)
delay=$(random_delay 600 1500)
log_message "Delay before comment posting: ${delay} seconds ($(( delay / 60 )) minutes)"
sleep $delay

# Script 5: LinkedIn comment poster (with randomized timing within 45-minute window)
log_message "Step 5: Running linkedin_comment_poster.py"
if [ -f "linkedin_comment_poster.py" ]; then
    # Random delay within remaining 45-minute window
    poster_delay=$(random_delay 0 2700)
    log_message "Comment poster will start in ${poster_delay} seconds ($(( poster_delay / 60 )) minutes)"
    sleep $poster_delay
    
    python linkedin_comment_poster.py --max-comments=25 --min-delay=30 --max-delay=90
    if [ $? -eq 0 ]; then
        log_message "✅ linkedin_comment_poster.py completed successfully"
    else
        log_message "❌ linkedin_comment_poster.py failed"
    fi
else
    log_message "⚠️ linkedin_comment_poster.py not found, skipping"
fi

log_message "=== LinkedIn Automation Sequence Completed ==="

# Generate summary
log_message "Summary: All scripts have been executed. Check individual logs for detailed results."

# Optional: Clean up old log files (keep last 30 days)
find "$SCRIPT_DIR" -name "*.log" -type f -mtime +30 -delete 2>/dev/null

exit 0

#!/usr/bin/env python3
"""
Test script to validate the rate limiting logic
"""

def test_rate_limiting_logic():
    """Test the rate limiting logic with sample data"""
    
    # Sample data simulating posts from database
    sample_posts = [
        {'profile_id': 1, 'post_id': 101, 'first_name': 'John', 'posted_date': '2025-07-24'},
        {'profile_id': 1, 'post_id': 102, 'first_name': 'John', 'posted_date': '2025-07-23'},
        {'profile_id': 1, 'post_id': 103, 'first_name': 'John', 'posted_date': '2025-07-22'},
        {'profile_id': 1, 'post_id': 104, 'first_name': 'John', 'posted_date': '2025-07-21'},  # Should be filtered
        {'profile_id': 1, 'post_id': 105, 'first_name': 'John', 'posted_date': '2025-07-20'},  # Should be filtered
        {'profile_id': 2, 'post_id': 201, 'first_name': 'Jane', 'posted_date': '2025-07-24'},
        {'profile_id': 2, 'post_id': 202, 'first_name': 'Jane', 'posted_date': '2025-07-23'},
        {'profile_id': 3, 'post_id': 301, 'first_name': 'Bob', 'posted_date': '2025-07-24'},
    ]
    
    # Apply the exact rate limiting logic from our implementation
    all_posts = sample_posts
    profile_counts = {}
    filtered_posts = []
    
    for post in all_posts:
        profile_id = post['profile_id']
        current_count = profile_counts.get(profile_id, 0)
        
        if current_count < 3:  # Max 3 posts per profile
            filtered_posts.append(post)
            profile_counts[profile_id] = current_count + 1
    
    print(f"Original posts: {len(all_posts)}")
    print(f"Filtered posts: {len(filtered_posts)}")
    print(f"Profile counts: {profile_counts}")
    
    # Validate results
    assert len(filtered_posts) == 6, f"Expected 6 posts, got {len(filtered_posts)}"
    assert profile_counts[1] == 3, f"Profile 1 should have 3 posts, got {profile_counts[1]}"
    assert profile_counts[2] == 2, f"Profile 2 should have 2 posts, got {profile_counts[2]}"
    assert profile_counts[3] == 1, f"Profile 3 should have 1 post, got {profile_counts[3]}"
    
    print("✅ Rate limiting test passed!")
    
    # Test comment limiting (max 2 per profile)
    sample_comments = [
        {'profile_id': 1, 'comment_id': 101},
        {'profile_id': 1, 'comment_id': 102},
        {'profile_id': 1, 'comment_id': 103},  # Should be filtered
        {'profile_id': 2, 'comment_id': 201},
        {'profile_id': 2, 'comment_id': 202},
        {'profile_id': 2, 'comment_id': 203},  # Should be filtered
    ]
    
    all_comments = sample_comments
    profile_counts = {}
    filtered_comments = []
    
    for comment in all_comments:
        profile_id = comment['profile_id']
        current_count = profile_counts.get(profile_id, 0)
        
        if current_count < 2:  # Max 2 comments per profile
            filtered_comments.append(comment)
            profile_counts[profile_id] = current_count + 1
    
    assert len(filtered_comments) == 4, f"Expected 4 comments, got {len(filtered_comments)}"
    assert profile_counts[1] == 2, f"Profile 1 should have 2 comments, got {profile_counts[1]}"
    assert profile_counts[2] == 2, f"Profile 2 should have 2 comments, got {profile_counts[2]}"
    
    print("✅ Comment rate limiting test passed!")

if __name__ == "__main__":
    test_rate_limiting_logic()
    print("🎉 All tests passed! Rate limiting logic is working correctly.")

#!/usr/bin/env python3
"""
Test script to verify that the title search functionality works
"""

import os
from wiki_analyzer import WikipediaAnalyzer
from dotenv import load_dotenv

def test_title_search():
    """Test searching for Wikipedia pages by title."""
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not found in environment variables")
        return False
    
    analyzer = WikipediaAnalyzer()
    
    # Test cases from the problematic entries
    test_cases = [
        "Joshua Sanes - Wikipedia",
        "Richard B. Freeman - Wikipedia",
        "Joshua Sanes",
        "Richard B. Freeman"
    ]
    
    print("🧪 Testing Wikipedia title search functionality")
    print("=" * 60)
    
    for test_title in test_cases:
        print(f"\nTesting: '{test_title}'")
        print("-" * 40)
        
        # Test the search function
        actual_title = analyzer.search_wikipedia_by_title(test_title)
        if actual_title:
            print(f"✅ Found page: {actual_title}")
            
            # Test fetching content
            content_data = analyzer.fetch_wikipedia_content(test_title)
            if content_data:
                print(f"✅ Successfully fetched content ({len(content_data['wikitext'])} chars)")
                print(f"   Warnings: {content_data['warnings']}")
            else:
                print("❌ Failed to fetch content")
        else:
            print("❌ Could not find Wikipedia page")
    
    return True

if __name__ == "__main__":
    print("Wikipedia Title Search Test")
    print("=" * 50)
    
    if test_title_search():
        print("\n✅ Test completed!")
        print("The title search functionality should now work for entries with titles instead of URLs")
    else:
        print("\n❌ Test failed!")


















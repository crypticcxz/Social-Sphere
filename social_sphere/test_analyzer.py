#!/usr/bin/env python3
"""
Test script for Wikipedia Analyzer
This script tests the analyzer with a single Wikipedia URL to verify functionality.
"""

import os
import sys
from wiki_analyzer import WikipediaAnalyzer
from dotenv import load_dotenv

def test_single_analysis():
    """Test the analyzer with a single Wikipedia URL."""
    load_dotenv()
    
    # Check if OpenAI API key is available
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEY not found in environment variables")
        print("Please create a .env file with your OpenAI API key")
        return False
    
    analyzer = WikipediaAnalyzer()
    
    # Test with a known Wikipedia URL
    test_url = "https://en.wikipedia.org/wiki/Q._Jane_Wang"
    print(f"Testing with URL: {test_url}")
    
    # Fetch content
    print("Fetching Wikipedia content...")
    content_data = analyzer.fetch_wikipedia_content(test_url)
    
    if not content_data:
        print("❌ Failed to fetch Wikipedia content")
        return False
    
    print("✅ Successfully fetched Wikipedia content")
    print(f"Content length: {len(content_data['wikitext'])} characters")
    print(f"Warnings detected: {content_data['warnings']}")
    
    # Test OpenAI analysis
    print("\nAnalyzing with OpenAI...")
    analysis = analyzer.analyze_with_openai("Q. Jane Wang", content_data)
    
    print("✅ Analysis completed!")
    print(f"Summary: {analysis['summary']}")
    print(f"Missing sections: {analysis['missing_sections']}")
    print(f"Warnings: {analysis['warnings']}")
    print(f"Assessment: {analysis['overall_assessment']}")
    
    return True

if __name__ == "__main__":
    print("Wikipedia Analyzer Test")
    print("=" * 50)
    
    if test_single_analysis():
        print("\n✅ Test completed successfully!")
        print("The analyzer is ready to process your full_name.csv file")
    else:
        print("\n❌ Test failed!")
        print("Please check your configuration and try again")


















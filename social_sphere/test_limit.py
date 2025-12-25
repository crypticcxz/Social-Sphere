#!/usr/bin/env python3
"""
Quick test script to demonstrate the --limit functionality
"""

import subprocess
import sys
import os

def test_with_limit():
    """Test the analyzer with a small limit."""
    print("🧪 Testing Wikipedia Analyzer with --limit functionality")
    print("=" * 60)
    
    # Check if the required files exist
    if not os.path.exists("full_name.csv"):
        print("❌ full_name.csv not found in current directory")
        return False
    
    if not os.path.exists(".env"):
        print("❌ .env file not found")
        print("Please create a .env file with your OPENAI_API_KEY")
        return False
    
    print("✅ Required files found")
    print("\n🚀 Running analyzer with --limit 3")
    print("This will process only the first 3 entries from full_name.csv")
    print("\n" + "="*60)
    
    try:
        # Run the analyzer with limit 3
        result = subprocess.run([
            sys.executable, "wiki_analyzer.py", "--limit", "3"
        ], capture_output=True, text=True, timeout=300)
        
        print("STDOUT:")
        print(result.stdout)
        
        if result.stderr:
            print("STDERR:")
            print(result.stderr)
        
        if result.returncode == 0:
            print("\n✅ Test completed successfully!")
            if os.path.exists("full_name_with_analysis.csv"):
                print("📄 Output file created: full_name_with_analysis.csv")
                # Count lines in output
                with open("full_name_with_analysis.csv", 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    print(f"📊 Output file has {len(lines)} lines (including header)")
            return True
        else:
            print(f"\n❌ Test failed with return code {result.returncode}")
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Test timed out after 5 minutes")
        return False
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

if __name__ == "__main__":
    success = test_with_limit()
    
    if success:
        print("\n🎉 Test passed! You can now:")
        print("1. Check the output file to see the analysis results")
        print("2. Run with different limits: --limit 10, --limit 50, etc.")
        print("3. Run without --limit to process all entries")
    else:
        print("\n💡 Troubleshooting tips:")
        print("1. Make sure you have a .env file with OPENAI_API_KEY")
        print("2. Check that full_name.csv exists in the current directory")
        print("3. Verify your OpenAI API key is valid and has credits")


















#!/usr/bin/env python3
"""
Test LLM configuration without running the full CLI.
"""

import os
from shared.config import get_settings

def test_llm_config():
    """Test that LLM environment variables are working."""

    print("🔧 Testing LLM Configuration...")
    print("=" * 50)

    # Test environment variables
    print("Environment Variables:")
    print(f"  LLM_BASE_URL: {os.getenv('LLM_BASE_URL', 'Not set')}")
    print(f"  LLM_AUTH_TOKEN: {'Set' if os.getenv('LLM_AUTH_TOKEN') else 'Not set'}")
    print(f"  LLM_MODEL: {os.getenv('LLM_MODEL', 'Not set')}")

    print("\nConfiguration:")
    settings = get_settings()
    print(f"  Base URL: {settings.llm_base_url}")
    print(f"  Model: {settings.llm_model}")
    print(f"  Auth Token: {'Set' if settings.llm_auth_token else 'Not set'}")
    print(f"  Model Config: {settings.get_llm_model_config()}")

    print("\nConfiguration Status:")
    if settings.llm_model == "test":
        print("  ✅ Test mode enabled - no API required")
        print("  ✅ Ready for Hebrew language testing")
    elif settings.llm_auth_token and settings.llm_model:
        print("  ✅ LLM API configured")
        print("  ✅ Ready for full AI processing")
    else:
        print("  ❌ LLM not properly configured")
        print("  💡 Set environment variables or use LLM_MODEL=test")

    print("\n🎯 Usage Examples:")
    if settings.llm_model == "test":
        print("  # Test Hebrew language support (no API)")
        print("  uv run python demo_hebrew.py")
        print("  ")
        print("  # Test CLI with mock processing")
        print("  LLM_MODEL=test uv run python -c 'from shared.config import get_settings; print(\"Config OK:\", get_settings().get_llm_model_config())'")
    else:
        print("  # Run with real AI")
        print("  LLM_BASE_URL=... LLM_AUTH_TOKEN=... LLM_MODEL=... uv run python -m interfaces.cli.main process -l he -d 'עוף צלוי'")

if __name__ == "__main__":
    test_llm_config()
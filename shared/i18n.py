"""
Internationalization (i18n) support for Holiday Meal Planner.

Provides localized text for CLI output, error messages, and user interfaces
with support for Hebrew (RTL) and English (LTR) languages.
"""

import json
import os
from typing import Dict, Any, Optional
from enum import Enum
from pathlib import Path


class Language(str, Enum):
    """Supported languages."""
    ENGLISH = "en"
    HEBREW = "he"


class LocalizationManager:
    """
    Manager for localized text strings.

    Supports loading and retrieving localized strings with fallback
    to English for missing translations.
    """

    def __init__(self, language: Language = Language.ENGLISH):
        """Initialize with specified language."""
        self.language = language
        self.translations: Dict[str, Dict[str, str]] = {}
        self._load_translations()

    def _load_translations(self) -> None:
        """Load translation files from the locales directory."""
        locales_dir = Path(__file__).parent / "locales"

        # Load English (default)
        en_file = locales_dir / "en.json"
        if en_file.exists():
            with open(en_file, "r", encoding="utf-8") as f:
                self.translations["en"] = json.load(f)
        else:
            self.translations["en"] = {}

        # Load Hebrew
        he_file = locales_dir / "he.json"
        if he_file.exists():
            with open(he_file, "r", encoding="utf-8") as f:
                self.translations["he"] = json.load(f)
        else:
            self.translations["he"] = {}

    def get_text(self, key: str, **kwargs) -> str:
        """
        Get localized text by key with optional formatting.

        Args:
            key: Translation key (e.g., "grocery_list.header")
            **kwargs: Format arguments for string interpolation

        Returns:
            Localized text string, falling back to English if not found
        """
        # Try current language first
        text = self._get_nested_value(self.translations.get(self.language.value, {}), key)

        # Fallback to English
        if not text and self.language != Language.ENGLISH:
            text = self._get_nested_value(self.translations.get("en", {}), key)

        # Ultimate fallback to key itself
        if not text:
            text = key

        # Apply formatting if provided
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, ValueError):
                # If formatting fails, return unformatted text
                return text

        return text

    def _get_nested_value(self, data: Dict, key: str) -> Optional[str]:
        """Get value from nested dictionary using dot notation."""
        keys = key.split(".")
        current = data

        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return None

        return current if isinstance(current, str) else None

    def set_language(self, language: Language) -> None:
        """Change the active language."""
        self.language = language
        self._load_translations()  # Reload in case files changed

    def is_rtl(self) -> bool:
        """Check if current language is right-to-left."""
        return self.language == Language.HEBREW

    def get_category_name(self, category: str) -> str:
        """Get localized category name."""
        return self.get_text(f"categories.{category}")

    def get_unit_name(self, unit: str) -> str:
        """Get localized unit name."""
        return self.get_text(f"units.{unit}")


# Global instance for easy access
_localization_manager = LocalizationManager()


def get_text(key: str, **kwargs) -> str:
    """Convenience function to get localized text."""
    return _localization_manager.get_text(key, **kwargs)


def set_language(language: Language) -> None:
    """Convenience function to set language."""
    _localization_manager.set_language(language)


def get_language() -> Language:
    """Get current language."""
    return _localization_manager.language


def is_rtl() -> bool:
    """Check if current language is RTL."""
    return _localization_manager.is_rtl()


def get_category_name(category: str) -> str:
    """Get localized category name."""
    return _localization_manager.get_category_name(category)


def get_unit_name(unit: str) -> str:
    """Get localized unit name."""
    return _localization_manager.get_unit_name(unit)
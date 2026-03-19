"""
Secure web extraction service for Holiday Meal Planner.

Implements cascade extraction strategy with security-first approach:
1. JSON-LD extraction (primary) - Schema.org Recipe markup
2. Microdata extraction (secondary) - HTML microdata attributes
3. HTML pattern matching (fallback) - CSS selectors and regex patterns
4. AI/LLM extraction (last resort) - When structured data unavailable

Security constraints align with constitutional requirements for HTTPS-only access.
"""

import time
import json
import re
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse, urljoin
import asyncio
import logging

import requests
from bs4 import BeautifulSoup
from extruct import extract
from recipe_scrapers import scrape_me
from recipe_scrapers import WebsiteNotImplementedError as RecipeScrapersException

from shared.exceptions import (
    RecipeParsingError,
    SecurityError,
    WebScrapingError,
    ValidationError
)
from shared.validators import validate_url_security
from shared.config import get_settings


logger = logging.getLogger(__name__)


class WebExtractor:
    """
    Secure web extraction service with cascade strategy.

    Extracts recipe information from URLs using multiple fallback methods
    with comprehensive security validation and rate limiting.
    """

    def __init__(self):
        """Initialize web extractor with security settings."""
        self.settings = get_settings()
        self.session = requests.Session()

        # Security headers for web requests
        self.session.headers.update({
            'User-Agent': 'Holiday-Meal-Planner/1.0 (+https://github.com/your-org/holiday-meal-planner)',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })

        # Rate limiting state
        self.last_request_time = 0.0
        self.min_request_interval = 1.5  # 1.5 seconds between requests

    async def extract_recipe(self, url: str) -> Dict[str, Any]:
        """
        Extract recipe information from URL using cascade strategy.

        Args:
            url: Recipe URL to extract from

        Returns:
            Dictionary containing extracted recipe information

        Raises:
            SecurityError: If URL fails security validation
            WebScrapingError: If web request fails
            RecipeParsingError: If no extraction method succeeds
        """
        # Security validation
        self._validate_url_security(url)

        # Rate limiting
        await self._respect_rate_limit()

        logger.info(f"Starting recipe extraction from: {url}")

        # Get HTML content
        html_content = await self._fetch_html(url)

        # Try extraction methods in order
        extraction_methods = [
            self._extract_with_recipe_scrapers,
            self._extract_with_json_ld,
            self._extract_with_microdata,
            self._extract_with_html_patterns,
        ]

        last_error = None
        for method in extraction_methods:
            try:
                result = await method(url, html_content)
                if result and self._validate_extraction_result(result):
                    logger.info(f"Successful extraction using {method.__name__}")
                    result['extraction_method'] = method.__name__
                    result['source_url'] = url
                    return result

            except Exception as e:
                last_error = e
                logger.warning(f"Extraction method {method.__name__} failed: {str(e)}")
                continue

        # All methods failed
        raise RecipeParsingError(
            f"All extraction methods failed for URL: {url}",
            url=url,
            details={'last_error': str(last_error) if last_error else 'No specific error'}
        )

    def _validate_url_security(self, url: str) -> None:
        """
        Validate URL meets security requirements.

        Args:
            url: URL to validate

        Raises:
            SecurityError: If URL fails security checks
        """
        # Use shared validator
        try:
            validate_url_security(url)
        except ValidationError as e:
            raise SecurityError(
                f"URL failed security validation: {e.message}",
                security_check="url_validation",
                blocked_value=url
            )

        # Additional web scraping specific checks
        parsed = urlparse(url)

        # Block non-HTTPS URLs
        if parsed.scheme != 'https':
            raise SecurityError(
                "Only HTTPS URLs are allowed",
                security_check="https_only",
                blocked_value=url
            )

        # Block suspicious domains
        suspicious_domains = [
            'localhost', '127.0.0.1', '0.0.0.0',
            '192.168.', '10.', '172.16.'
        ]

        for suspicious in suspicious_domains:
            if suspicious in parsed.netloc:
                raise SecurityError(
                    f"Blocked suspicious domain: {parsed.netloc}",
                    security_check="domain_blacklist",
                    blocked_value=url
                )

    async def _respect_rate_limit(self) -> None:
        """Implement rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time

        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            await asyncio.sleep(sleep_time)

        self.last_request_time = time.time()

    async def _fetch_html(self, url: str) -> str:
        """
        Fetch HTML content from URL with security controls.

        Args:
            url: URL to fetch

        Returns:
            HTML content as string

        Raises:
            WebScrapingError: If request fails
        """
        try:
            # Use asyncio to handle the synchronous request
            response = await asyncio.to_thread(
                self.session.get,
                url,
                timeout=self.settings.request_timeout,
                allow_redirects=True
            )

            # Validate response
            response.raise_for_status()

            # Check content length
            if len(response.content) > self.settings.max_response_size:
                raise WebScrapingError(
                    f"Response too large: {len(response.content)} bytes",
                    url=url,
                    details={'max_size': self.settings.max_response_size}
                )

            # Validate content type
            content_type = response.headers.get('content-type', '').lower()
            if not any(ct in content_type for ct in ['text/html', 'application/xhtml']):
                raise WebScrapingError(
                    f"Invalid content type: {content_type}",
                    url=url,
                    details={'content_type': content_type}
                )

            return response.text

        except requests.exceptions.Timeout:
            raise WebScrapingError(
                f"Request timeout after {self.settings.request_timeout} seconds",
                url=url,
                timeout_seconds=self.settings.request_timeout
            )

        except requests.exceptions.HTTPError as e:
            raise WebScrapingError(
                f"HTTP error: {e.response.status_code}",
                url=url,
                http_status=e.response.status_code
            )

        except requests.exceptions.RequestException as e:
            raise WebScrapingError(
                f"Request failed: {str(e)}",
                url=url,
                details={'request_error': str(e)}
            )

    async def _extract_with_recipe_scrapers(self, url: str, html_content: str) -> Dict[str, Any]:
        """
        Extract recipe using recipe-scrapers library (primary method).

        Args:
            url: Recipe URL
            html_content: HTML content (unused, but kept for interface consistency)

        Returns:
            Extracted recipe information

        Raises:
            RecipeParsingError: If extraction fails
        """
        try:
            # Use asyncio to handle the synchronous scraper
            scraper = await asyncio.to_thread(scrape_me, url)

            # Extract structured data
            result = {
                'title': scraper.title() or 'Unknown Recipe',
                'ingredients': scraper.ingredients() or [],
                'instructions': scraper.instructions_list() or [],
                'servings': self._parse_servings(scraper.yields()),
                'prep_time_minutes': self._parse_time(scraper.prep_time()),
                'cook_time_minutes': self._parse_time(scraper.cook_time()),
                'total_time_minutes': self._parse_time(scraper.total_time()),
                'description': scraper.description() or '',
                'image_url': scraper.image() or None,
                'confidence': 0.95  # High confidence for structured data
            }

            return result

        except RecipeScrapersException as e:
            raise RecipeParsingError(
                f"Recipe scrapers failed: {str(e)}",
                url=url,
                extraction_method="recipe_scrapers",
                details={'scraper_error': str(e)}
            )

    async def _extract_with_json_ld(self, url: str, html_content: str) -> Dict[str, Any]:
        """
        Extract recipe using JSON-LD structured data.

        Args:
            url: Recipe URL
            html_content: HTML content to parse

        Returns:
            Extracted recipe information

        Raises:
            RecipeParsingError: If extraction fails
        """
        try:
            # Extract structured data
            structured_data = extract(html_content, base_url=url)
            json_ld_data = structured_data.get('json-ld', [])

            # Find Recipe schema
            recipe_data = None
            for item in json_ld_data:
                if isinstance(item, dict):
                    item_type = item.get('@type', '')
                    if item_type == 'Recipe' or 'Recipe' in str(item_type):
                        recipe_data = item
                        break

            if not recipe_data:
                raise RecipeParsingError(
                    "No Recipe JSON-LD found",
                    url=url,
                    extraction_method="json_ld"
                )

            # Parse recipe data
            result = {
                'title': recipe_data.get('name', 'Unknown Recipe'),
                'ingredients': self._parse_json_ld_ingredients(recipe_data.get('recipeIngredient', [])),
                'instructions': self._parse_json_ld_instructions(recipe_data.get('recipeInstructions', [])),
                'servings': self._parse_servings(recipe_data.get('recipeYield')),
                'prep_time_minutes': self._parse_iso_duration(recipe_data.get('prepTime')),
                'cook_time_minutes': self._parse_iso_duration(recipe_data.get('cookTime')),
                'total_time_minutes': self._parse_iso_duration(recipe_data.get('totalTime')),
                'description': recipe_data.get('description', ''),
                'image_url': self._extract_image_url(recipe_data.get('image')),
                'confidence': 0.9  # High confidence for structured data
            }

            return result

        except Exception as e:
            raise RecipeParsingError(
                f"JSON-LD extraction failed: {str(e)}",
                url=url,
                extraction_method="json_ld",
                details={'parse_error': str(e)}
            )

    async def _extract_with_microdata(self, url: str, html_content: str) -> Dict[str, Any]:
        """
        Extract recipe using microdata.

        Args:
            url: Recipe URL
            html_content: HTML content to parse

        Returns:
            Extracted recipe information

        Raises:
            RecipeParsingError: If extraction fails
        """
        try:
            structured_data = extract(html_content, base_url=url)
            microdata = structured_data.get('microdata', [])

            # Find Recipe microdata
            recipe_data = None
            for item in microdata:
                if isinstance(item, dict):
                    item_type = item.get('type', '')
                    if 'Recipe' in str(item_type):
                        recipe_data = item.get('properties', {})
                        break

            if not recipe_data:
                raise RecipeParsingError(
                    "No Recipe microdata found",
                    url=url,
                    extraction_method="microdata"
                )

            # Parse microdata
            result = {
                'title': self._get_microdata_text(recipe_data.get('name', ['Unknown Recipe'])),
                'ingredients': self._parse_microdata_list(recipe_data.get('recipeIngredient', [])),
                'instructions': self._parse_microdata_list(recipe_data.get('recipeInstructions', [])),
                'servings': self._parse_servings(self._get_microdata_text(recipe_data.get('recipeYield', []))),
                'prep_time_minutes': self._parse_iso_duration(self._get_microdata_text(recipe_data.get('prepTime', []))),
                'cook_time_minutes': self._parse_iso_duration(self._get_microdata_text(recipe_data.get('cookTime', []))),
                'total_time_minutes': self._parse_iso_duration(self._get_microdata_text(recipe_data.get('totalTime', []))),
                'description': self._get_microdata_text(recipe_data.get('description', [''])),
                'image_url': self._get_microdata_text(recipe_data.get('image', [None])),
                'confidence': 0.8  # Good confidence for microdata
            }

            return result

        except Exception as e:
            raise RecipeParsingError(
                f"Microdata extraction failed: {str(e)}",
                url=url,
                extraction_method="microdata",
                details={'parse_error': str(e)}
            )

    async def _extract_with_html_patterns(self, url: str, html_content: str) -> Dict[str, Any]:
        """
        Extract recipe using HTML pattern matching (fallback).

        Args:
            url: Recipe URL
            html_content: HTML content to parse

        Returns:
            Extracted recipe information

        Raises:
            RecipeParsingError: If extraction fails
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # Common selectors for recipe sites
            title_selectors = [
                'h1.recipe-title', 'h1[class*="title"]', 'h1[class*="recipe"]',
                '.entry-title', '.recipe-header h1', 'h1'
            ]

            ingredient_selectors = [
                '.recipe-ingredients li', '.ingredients li', '[class*="ingredient"]',
                '.recipe-ingredient', '.ingredient-list li'
            ]

            instruction_selectors = [
                '.recipe-instructions li', '.instructions li', '[class*="instruction"]',
                '.recipe-instruction', '.instruction-list li', '.directions li'
            ]

            # Extract components
            title = self._extract_by_selectors(soup, title_selectors)
            ingredients = self._extract_list_by_selectors(soup, ingredient_selectors)
            instructions = self._extract_list_by_selectors(soup, instruction_selectors)

            if not title and not ingredients:
                raise RecipeParsingError(
                    "Could not extract basic recipe information",
                    url=url,
                    extraction_method="html_patterns"
                )

            result = {
                'title': title or 'Unknown Recipe',
                'ingredients': ingredients or [],
                'instructions': instructions or [],
                'servings': None,  # Hard to extract reliably
                'prep_time_minutes': None,
                'cook_time_minutes': None,
                'total_time_minutes': None,
                'description': '',
                'image_url': None,
                'confidence': 0.6  # Lower confidence for pattern matching
            }

            return result

        except Exception as e:
            raise RecipeParsingError(
                f"HTML pattern extraction failed: {str(e)}",
                url=url,
                extraction_method="html_patterns",
                details={'parse_error': str(e)}
            )

    def _validate_extraction_result(self, result: Dict[str, Any]) -> bool:
        """
        Validate that extraction result contains minimum required data.

        Args:
            result: Extraction result to validate

        Returns:
            True if result is valid
        """
        # Must have title and at least one ingredient
        if not result.get('title') or not result.get('ingredients'):
            return False

        # Ingredients must be a non-empty list
        ingredients = result.get('ingredients', [])
        if not isinstance(ingredients, list) or len(ingredients) == 0:
            return False

        return True

    # Utility methods for parsing different data formats

    def _parse_servings(self, servings_text: Any) -> Optional[int]:
        """Parse serving size from various text formats."""
        if not servings_text:
            return None

        text = str(servings_text).lower()
        # Look for numbers
        numbers = re.findall(r'\d+', text)
        return int(numbers[0]) if numbers else None

    def _parse_time(self, time_value: Any) -> Optional[int]:
        """Parse time duration in minutes."""
        if not time_value:
            return None

        if isinstance(time_value, int):
            return time_value

        text = str(time_value).lower()

        # Look for patterns like "1 hour 30 minutes" or "90 minutes"
        minutes = 0

        hours = re.findall(r'(\d+)\s*(?:hour|hr)', text)
        if hours:
            minutes += int(hours[0]) * 60

        mins = re.findall(r'(\d+)\s*(?:minute|min)', text)
        if mins:
            minutes += int(mins[0])

        return minutes if minutes > 0 else None

    def _parse_iso_duration(self, duration: Any) -> Optional[int]:
        """Parse ISO 8601 duration to minutes."""
        if not duration:
            return None

        text = str(duration).upper()
        if not text.startswith('PT'):
            return self._parse_time(duration)  # Fallback to regular parsing

        # Parse PT1H30M format
        minutes = 0

        hours = re.findall(r'(\d+)H', text)
        if hours:
            minutes += int(hours[0]) * 60

        mins = re.findall(r'(\d+)M', text)
        if mins:
            minutes += int(mins[0])

        return minutes if minutes > 0 else None

    def _parse_json_ld_ingredients(self, ingredients: List) -> List[str]:
        """Parse ingredients from JSON-LD format."""
        result = []
        for ingredient in ingredients:
            if isinstance(ingredient, str):
                result.append(ingredient.strip())
            elif isinstance(ingredient, dict):
                # Sometimes ingredients are objects with text property
                text = ingredient.get('text', ingredient.get('name', str(ingredient)))
                result.append(text.strip())
        return [ing for ing in result if ing]

    def _parse_json_ld_instructions(self, instructions: List) -> List[str]:
        """Parse instructions from JSON-LD format."""
        result = []
        for instruction in instructions:
            if isinstance(instruction, str):
                result.append(instruction.strip())
            elif isinstance(instruction, dict):
                text = instruction.get('text', instruction.get('name', str(instruction)))
                result.append(text.strip())
        return [inst for inst in result if inst]

    def _extract_image_url(self, image_data: Any) -> Optional[str]:
        """Extract image URL from various formats."""
        if not image_data:
            return None

        if isinstance(image_data, str):
            return image_data

        if isinstance(image_data, list) and image_data:
            return self._extract_image_url(image_data[0])

        if isinstance(image_data, dict):
            return image_data.get('url', image_data.get('contentUrl'))

        return None

    def _get_microdata_text(self, data: List) -> str:
        """Extract text from microdata list format."""
        if not data:
            return ''

        if isinstance(data, list) and data:
            return str(data[0])

        return str(data)

    def _parse_microdata_list(self, data: List) -> List[str]:
        """Parse list data from microdata format."""
        result = []
        for item in data:
            if isinstance(item, str):
                result.append(item.strip())
            elif isinstance(item, dict):
                text = item.get('properties', {}).get('text', [str(item)])[0]
                result.append(text.strip())
        return [item for item in result if item]

    def _extract_by_selectors(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
        """Extract text using CSS selectors."""
        for selector in selectors:
            try:
                element = soup.select_one(selector)
                if element:
                    text = element.get_text(strip=True)
                    if text:
                        return text
            except Exception:
                continue
        return None

    def _extract_list_by_selectors(self, soup: BeautifulSoup, selectors: List[str]) -> List[str]:
        """Extract list of text using CSS selectors."""
        for selector in selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    texts = [elem.get_text(strip=True) for elem in elements]
                    texts = [text for text in texts if text]
                    if texts:
                        return texts
            except Exception:
                continue
        return []


# Convenience function for external usage
async def extract_recipe_from_url(url: str) -> Dict[str, Any]:
    """
    Extract recipe information from URL.

    Convenience function that creates a WebExtractor instance and extracts
    recipe data with all security and validation checks.

    Args:
        url: Recipe URL to extract from

    Returns:
        Dictionary containing extracted recipe information

    Raises:
        SecurityError: If URL fails security validation
        WebScrapingError: If web request fails
        RecipeParsingError: If no extraction method succeeds
    """
    extractor = WebExtractor()
    return await extractor.extract_recipe(url)
"""
File categorization utility for IFMOS.
Provides hierarchical file classification based on extensions and MIME types.
"""

import yaml
from pathlib import Path
from typing import Dict, Tuple, Optional


class FileCategorizer:
    """
    Categorizes files into hierarchical categories and subcategories.
    """

    def __init__(self, config_path: str = None):
        """
        Initialize categorizer with category definitions.

        Args:
            config_path: Path to file_categories.yml (optional)
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / 'config' / 'file_categories.yml'

        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Build extension-to-category mapping for fast lookup
        self._ext_to_category = {}
        self._ext_to_subcategory = {}
        self._build_extension_map()

    def _build_extension_map(self):
        """Build reverse lookup map from extension to category/subcategory."""
        categories = self.config.get('categories', {})

        for category_name, category_data in categories.items():
            subcategories = category_data.get('subcategories', {})

            for subcat_name, subcat_data in subcategories.items():
                extensions = subcat_data.get('extensions', [])

                for ext in extensions:
                    ext_lower = ext.lower()
                    self._ext_to_category[ext_lower] = category_name
                    self._ext_to_subcategory[ext_lower] = subcat_name

    def categorize(self, extension: str, mime_type: Optional[str] = None,
                   filename: Optional[str] = None) -> Tuple[str, str]:
        """
        Categorize a file based on extension, MIME type, and filename.

        Args:
            extension: File extension (e.g., '.pdf')
            mime_type: Optional MIME type string
            filename: Optional filename for pattern matching

        Returns:
            Tuple of (category, subcategory)
        """
        ext_lower = extension.lower()

        # Check special patterns first
        if filename:
            special_cat = self._check_special_patterns(filename)
            if special_cat:
                return special_cat

        # Try extension-based lookup
        if ext_lower in self._ext_to_category:
            category = self._ext_to_category[ext_lower]
            subcategory = self._ext_to_subcategory[ext_lower]
            return (category, subcategory)

        # Fallback to MIME type
        if mime_type:
            category = self._categorize_by_mime(mime_type)
            if category:
                return (category, 'other')

        # Default to 'other'
        return ('other', 'unknown')

    def _check_special_patterns(self, filename: str) -> Optional[Tuple[str, str]]:
        """
        Check if filename matches special patterns.

        Args:
            filename: Filename to check

        Returns:
            Tuple of (category, subcategory) or None
        """
        import fnmatch

        special_patterns = self.config.get('special_patterns', {})

        # Check temp patterns
        temp_patterns = special_patterns.get('temp_patterns', [])
        for pattern in temp_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return ('system', 'temp_files')

        # Check low-value patterns
        low_value_patterns = special_patterns.get('low_value_patterns', [])
        for pattern in low_value_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return ('system', 'logs')

        return None

    def _categorize_by_mime(self, mime_type: str) -> Optional[str]:
        """
        Categorize by MIME type prefix.

        Args:
            mime_type: MIME type string

        Returns:
            Category name or None
        """
        mime_fallbacks = self.config.get('mime_type_fallbacks', {})

        for mime_prefix, category in mime_fallbacks.items():
            if mime_type.startswith(mime_prefix):
                return category

        return None

    def get_category_description(self, category: str) -> str:
        """Get description for a category."""
        categories = self.config.get('categories', {})
        cat_data = categories.get(category, {})
        return cat_data.get('description', 'No description')

    def get_subcategory_description(self, category: str, subcategory: str) -> str:
        """Get description for a subcategory."""
        categories = self.config.get('categories', {})
        cat_data = categories.get(category, {})
        subcats = cat_data.get('subcategories', {})
        subcat_data = subcats.get(subcategory, {})
        return subcat_data.get('description', 'No description')

    def get_all_categories(self) -> Dict:
        """Get all categories and their subcategories."""
        return self.config.get('categories', {})

    def get_extensions_for_category(self, category: str, subcategory: str = None) -> list:
        """
        Get all extensions for a category or subcategory.

        Args:
            category: Category name
            subcategory: Optional subcategory name

        Returns:
            List of extensions
        """
        categories = self.config.get('categories', {})
        cat_data = categories.get(category, {})

        if subcategory:
            subcats = cat_data.get('subcategories', {})
            subcat_data = subcats.get(subcategory, {})
            return subcat_data.get('extensions', [])
        else:
            # Return all extensions in category
            extensions = []
            subcats = cat_data.get('subcategories', {})
            for subcat_data in subcats.values():
                extensions.extend(subcat_data.get('extensions', []))
            return extensions

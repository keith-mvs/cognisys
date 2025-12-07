"""
Content Extraction Module - Enhanced
Handles PDF, Office documents, images, code, HTML, PowerPoint, and configs with OCR fallback
"""

import logging
from typing import Dict, List, Optional
from pathlib import Path
import mimetypes
import re

try:
    import PyPDF2
    from pdf2image import convert_from_path
    import pdfplumber
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    from docx import Document
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    import openpyxl
    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from pptx import Presentation
    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# Code continued...

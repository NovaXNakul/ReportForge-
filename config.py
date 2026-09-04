# config.py

"""
Global Configuration Settings for XToP & Web Scraper Pipeline.
Defines styling themes, slide dimensions, font sizes, and directory paths.
"""

import os
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

# ==========================================
# Paths Configuration
# ==========================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")

DEFAULT_CSV_PATH = os.path.join(DATA_DIR, "books_data.csv")
DEFAULT_EXCEL_PATH = os.path.join(OUTPUT_DIR, "books_report.xlsx")
DEFAULT_PPT_PATH = os.path.join(OUTPUT_DIR, "report.pptx")

# Ensure required directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ==========================================
# Styling & Theme Tokens
# ==========================================

# Colors (Hex & RGB)
COLOR_PRIMARY_HEX = "1F4E78"      # Deep Navy Blue
COLOR_SECONDARY_HEX = "2E75B6"    # Steel Blue
COLOR_ACCENT_HEX = "595959"       # Muted Dark Gray
COLOR_BG_CARD_HEX = "F2F4F7"      # Light Gray Card Background
COLOR_TEXT_HEX = "333333"         # Dark Gray Text

PRIMARY_COLOR = RGBColor(31, 78, 120)     # Navy Blue
SECONDARY_COLOR = RGBColor(46, 117, 182)  # Steel Blue
ACCENT_COLOR = RGBColor(89, 89, 89)       # Dark Gray
WHITE_COLOR = RGBColor(255, 255, 255)
DARK_COLOR = RGBColor(51, 51, 51)

# Typography
FONT_NAME = "Calibri"
TITLE_FONT_SIZE = Pt(28)
SUBTITLE_FONT_SIZE = Pt(18)
BODY_FONT_SIZE = Pt(14)
CARD_VALUE_FONT_SIZE = Pt(22)
CARD_TITLE_FONT_SIZE = Pt(12)

# Slide Layout Constants (Inches)
SLIDE_WIDTH = Inches(10)
SLIDE_HEIGHT = Inches(7.5)
MARGIN_LEFT = Inches(0.8)
MARGIN_TOP = Inches(1.2)
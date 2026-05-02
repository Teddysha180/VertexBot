import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Logging configuration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))

# AI Configuration
GROQ_API_KEY = os.getenv('GROQ_API_KEY')
GROQ_MODEL = "mixtral-8x7b-32768"

# Google Sheets Configuration (optional for testing)
USE_GOOGLE_SHEETS = os.getenv('USE_GOOGLE_SHEETS', 'False').lower() == 'true'
GOOGLE_SHEETS_CREDENTIALS = os.getenv('GOOGLE_SHEETS_CREDENTIALS', 'credentials.json')
SHEET_NAME = os.getenv('SHEET_NAME', 'VertexSACCO')

# Local database file (fallback when not using Google Sheets)
DB_FILE = 'vertex_bot_data.json'

# Branch Locations
BRANCHES = {
    'headquarters': {
        'name': 'Headquarters',
        'address': '123 Business District, Nairobi, Kenya',
        'maps_link': 'https://maps.google.com/?q=123+Business+District+Nairobi',
        'hours': 'Mon-Fri: 8:00 AM - 5:00 PM',
        'phone': '+254 700 123 456'
    },
    'westlands': {
        'name': 'Westlands Branch',
        'address': '456 Westlands Road, Nairobi, Kenya',
        'maps_link': 'https://maps.google.com/?q=456+Westlands+Road+Nairobi',
        'hours': 'Mon-Fri: 8:30 AM - 4:30 PM, Sat: 9:00 AM - 1:00 PM',
        'phone': '+254 700 123 457'
    },
    'industrial': {
        'name': 'Industrial Area Branch',
        'address': '789 Enterprise Road, Nairobi, Kenya',
        'maps_link': 'https://maps.google.com/?q=789+Enterprise+Road+Nairobi',
        'hours': 'Mon-Fri: 8:00 AM - 4:00 PM',
        'phone': '+254 700 123 458'
    }
}

# Services Information
SERVICES = {
    'loans': {
        'types': [
            'Emergency Loan (24hrs approval)',
            'Business Loan (up to 5M KES)',
            'School Fees Loan',
            'Mortgage Loan',
            'Asset Financing'
        ],
        'requirements': [
            'Active membership (3+ months)',
            'Valid ID',
            'Latest 3 months bank statements',
            'Loan application form',
            'Collateral (for large loans)'
        ],
        'interest_rate': '1.5% - 2.5% per month reducing balance'
    },
    'savings': {
        'types': [
            'Ordinary Savings Account',
            'Fixed Deposit Account',
            'Target Savings Account',
            'Youth/Savings Account'
        ],
        'benefits': [
            'Competitive interest rates',
            'Dividend payments annually',
            'Emergency loan access',
            'Borrow up to 3x savings'
        ],
        'minimum_deposit': '1,000 KES'
    }
}
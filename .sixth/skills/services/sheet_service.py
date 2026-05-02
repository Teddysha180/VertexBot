import json
import os
from datetime import datetime
from typing import List, Dict, Optional
from config import logger, USE_GOOGLE_SHEETS, DB_FILE

class SheetService:
    """Handles data storage with Google Sheets or local JSON file"""
    
    def __init__(self, credentials_file: str = None, sheet_name: str = None):
        self.use_google_sheets = USE_GOOGLE_SHEETS
        self.db_file = DB_FILE
        
        if self.use_google_sheets:
            try:
                import gspread
                from google.oauth2.service_account import Credentials
                
                scope = ['https://spreadsheets.google.com/feeds',
                        'https://www.googleapis.com/auth/drive']
                creds = Credentials.from_service_account_file(credentials_file, scopes=scope)
                self.client = gspread.authorize(creds)
                self.sheet = self.client.open(sheet_name)
                self._initialize_sheets()
                logger.info("Google Sheets initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Google Sheets: {e}")
                logger.info("Falling back to local JSON storage")
                self.use_google_sheets = False
                self._init_local_db()
        else:
            self._init_local_db()
            logger.info("Using local JSON storage")
    
    def _init_local_db(self):
        """Initialize local JSON database"""
        if not os.path.exists(self.db_file):
            initial_data = {
                'FAQ': [],
                'Users': [],
                'Feedback': [],
                'Ratings': [],
                'Conversations': []
            }
            self._save_local_db(initial_data)
    
    def _save_local_db(self, data: dict):
        """Save data to local JSON file"""
        with open(self.db_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_local_db(self) -> dict:
        """Load data from local JSON file"""
        if os.path.exists(self.db_file):
            with open(self.db_file, 'r') as f:
                return json.load(f)
        return {'FAQ': [], 'Users': [], 'Feedback': [], 'Ratings': [], 'Conversations': []}
    
    def _initialize_sheets(self):
        """Create necessary worksheets if they don't exist"""
        required_sheets = ['FAQ', 'Users', 'Feedback', 'Ratings', 'Conversations']
        
        for sheet_name in required_sheets:
            try:
                self.sheet.worksheet(sheet_name)
            except:
                self.sheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
        
        self._init_headers()
    
    def _init_headers(self):
        """Initialize column headers for each worksheet"""
        headers = {
            'FAQ': ['Question', 'Answer', 'Category', 'Date Added', 'Added By'],
            'Users': ['User ID', 'Username', 'First Name', 'Last Name', 'Joined Date', 'Last Active'],
            'Feedback': ['User ID', 'Username', 'Message', 'Date', 'Status'],
            'Ratings': ['User ID', 'Username', 'Rating', 'Query', 'Date'],
            'Conversations': ['User ID', 'Question', 'Answer', 'Source', 'Date']
        }
        
        for sheet_name, cols in headers.items():
            worksheet = self.sheet.worksheet(sheet_name)
            if not worksheet.get_all_values():
                worksheet.append_row(cols)
    
    def save_user(self, user_id: int, username: str, first_name: str, last_name: str = ''):
        """Save or update user information"""
        if self.use_google_sheets:
            worksheet = self.sheet.worksheet('Users')
            users = worksheet.get_all_values()
            
            for i, user in enumerate(users[1:], start=2):
                if user and str(user[0]) == str(user_id):
                    worksheet.update(f'F{i}', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                    return
            
            worksheet.append_row([
                user_id, username or '', first_name or '', last_name or '',
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])
        else:
            data = self._load_local_db()
            user_exists = False
            for user in data['Users']:
                if user['user_id'] == user_id:
                    user['last_active'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    user_exists = True
                    break
            
            if not user_exists:
                data['Users'].append({
                    'user_id': user_id,
                    'username': username or '',
                    'first_name': first_name or '',
                    'last_name': last_name or '',
                    'joined_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'last_active': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                })
            
            self._save_local_db(data)
    
    def save_faq(self, question: str, answer: str, category: str = 'General', added_by: str = 'Admin'):
        """Save a new FAQ entry"""
        if self.use_google_sheets:
            worksheet = self.sheet.worksheet('FAQ')
            worksheet.append_row([
                question.lower(),
                answer,
                category,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                added_by
            ])
        else:
            data = self._load_local_db()
            data['FAQ'].append({
                'question': question.lower(),
                'answer': answer,
                'category': category,
                'date_added': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'added_by': added_by
            })
            self._save_local_db(data)
    
    def get_faq(self) -> List[Dict]:
        """Retrieve all FAQs"""
        if self.use_google_sheets:
            worksheet = self.sheet.worksheet('FAQ')
            records = worksheet.get_all_records()
            return records
        else:
            data = self._load_local_db()
            return data['FAQ']
    
    def search_faq(self, query: str) -> Optional[Dict]:
        """Search for matching FAQ based on keywords"""
        faqs = self.get_faq()
        query = query.lower()
        
        for faq in faqs:
            faq_question = faq.get('Question', faq.get('question', '')).lower()
            if query in faq_question:
                return faq
        
        return None
    
    def save_feedback(self, user_id: int, username: str, message: str):
        """Save user feedback"""
        if self.use_google_sheets:
            worksheet = self.sheet.worksheet('Feedback')
            worksheet.append_row([
                user_id, username or '', message,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'Pending'
            ])
        else:
            data = self._load_local_db()
            data['Feedback'].append({
                'user_id': user_id,
                'username': username or '',
                'message': message,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'status': 'Pending'
            })
            self._save_local_db(data)
    
    def save_rating(self, user_id: int, username: str, rating: int, query: str):
        """Save user rating"""
        if self.use_google_sheets:
            worksheet = self.sheet.worksheet('Ratings')
            worksheet.append_row([
                user_id, username or '', rating, query[:200],
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])
        else:
            data = self._load_local_db()
            data['Ratings'].append({
                'user_id': user_id,
                'username': username or '',
                'rating': rating,
                'query': query[:200],
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            self._save_local_db(data)
    
    def save_conversation(self, user_id: int, question: str, answer: str, source: str):
        """Save conversation history"""
        if self.use_google_sheets:
            worksheet = self.sheet.worksheet('Conversations')
            worksheet.append_row([
                user_id, question[:300], answer[:500], source,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ])
        else:
            data = self._load_local_db()
            data['Conversations'].append({
                'user_id': user_id,
                'question': question[:300],
                'answer': answer[:500],
                'source': source,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })
            self._save_local_db(data)
    
    def get_stats(self) -> Dict:
        """Get bot statistics"""
        if self.use_google_sheets:
            return {
                'total_users': len(self.sheet.worksheet('Users').get_all_values()) - 1,
                'total_conversations': len(self.sheet.worksheet('Conversations').get_all_values()) - 1,
                'total_faqs': len(self.sheet.worksheet('FAQ').get_all_values()) - 1
            }
        else:
            data = self._load_local_db()
            return {
                'total_users': len(data['Users']),
                'total_conversations': len(data['Conversations']),
                'total_faqs': len(data['FAQ'])
            }
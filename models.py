from datetime import datetime
import sqlite3
import json
import os
from typing import Optional, List
from google.cloud import storage
import tempfile
from dotenv import load_dotenv

load_dotenv()

class VocabDatabase:
    def __init__(self, db_path="vocab_learning.db", bucket_name="ian-line-bot-files"):
        self.is_cloud = os.getenv('ENV') == 'prod'
        
        if self.is_cloud:
            self.bucket_name = bucket_name
            self.db_name = db_path
            self.storage_client = storage.Client()
            self.bucket = self.storage_client.bucket(bucket_name)
            self.blob = self.bucket.blob(self.db_name)
            self.temp_db_path = None
            self.db_path = self._download_db() if self.is_cloud else None
        else:
            self.db_path = db_path
            
        self.init_db()

    def _download_db(self):
        """從 Cloud Storage 下載數據庫到臨時文件"""
        if not self.is_cloud:
            return self.db_path
            
        self.temp_db_path = tempfile.mktemp()
        if self.blob.exists():
            self.blob.download_to_filename(self.temp_db_path)
        return self.temp_db_path

    def _upload_db(self):
        """將臨時數據庫文件上傳到 Cloud Storage"""
        if not self.is_cloud:
            return
            
        if self.temp_db_path and os.path.exists(self.temp_db_path):
            self.blob.upload_from_filename(self.temp_db_path)
            os.remove(self.temp_db_path)
            self.temp_db_path = None

    def _get_db_path(self):
        """獲取當前應該使用的數據庫路徑"""
        return self._download_db() if self.is_cloud else self.db_path

    def init_db(self):
        """初始化資料庫表"""
        db_path = self._get_db_path()
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        # 用戶表
        c.execute('''CREATE TABLE IF NOT EXISTS users
                    (user_id TEXT PRIMARY KEY,
                     username TEXT UNIQUE NOT NULL,
                     created_at TIMESTAMP)''')
        
        # 用戶單字表
        c.execute('''CREATE TABLE IF NOT EXISTS user_vocabulary
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     user_id TEXT,
                     word TEXT,
                     definition TEXT,
                     examples TEXT,
                     notes TEXT,
                     created_at TIMESTAMP,
                     FOREIGN KEY (user_id) REFERENCES users(user_id))''')
        
        conn.commit()
        conn.close()
        
        if self.is_cloud:
            self._upload_db()

    def test_connection(self):
        """測試資料庫連接"""
        try:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            conn.close()
            if self.is_cloud:
                self._upload_db()
            return True
        except Exception:
            return False

    def get_or_create_user(self, username: str) -> str:
        """獲取或創建用戶"""
        db_path = self._get_db_path()
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        c.execute('SELECT user_id FROM users WHERE username = ?', (username,))
        result = c.fetchone()
        
        if result:
            user_id = result[0]
        else:
            user_id = username
            now = datetime.now()
            c.execute('''INSERT INTO users (user_id, username, created_at)
                        VALUES (?, ?, ?)''', (user_id, username, now))
        
        conn.commit()
        conn.close()
        
        if self.is_cloud:
            self._upload_db()
        return user_id

    def add_vocabulary(self, user_id: str, word: str, definition: str, 
                    examples: List[str], notes: str = ""):
        """添加新單字到用戶的詞彙表"""
        try:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            # 先檢查單字是否已存在
            if self.word_exists(user_id, word):
                conn.close()
                raise ValueError(f"單字 '{word}' 已經存在於您的單字本中")
                
            now = datetime.now()
            c.execute('''INSERT INTO user_vocabulary 
                        (user_id, word, definition, examples, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                    (user_id, word, definition, json.dumps(examples), notes, now))
            
            conn.commit()
            conn.close()
            
            if self.is_cloud:
                self._upload_db()
            return True
            
        except sqlite3.Error as e:
            raise Exception(f"資料庫錯誤：{str(e)}")
        except Exception as e:
            raise e

    def word_exists(self, user_id: str, word: str) -> bool:
        """檢查單字是否已經存在於用戶的單字本中"""
        db_path = self._get_db_path()
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        c.execute('''SELECT COUNT(*) FROM user_vocabulary 
                    WHERE user_id = ? AND word = ?''', (user_id, word))
        
        count = c.fetchone()[0]
        conn.close()
        
        if self.is_cloud:
            self._upload_db()
        
        return count > 0

    def get_user_vocabulary(self, user_id: str):
        """獲取用戶的詞彙表"""
        db_path = self._get_db_path()
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        
        c.execute('''SELECT * FROM user_vocabulary 
                    WHERE user_id = ?
                    ORDER BY created_at DESC''', (user_id,))
        
        results = c.fetchall()
        conn.close()
        
        if self.is_cloud:
            self._upload_db()
        
        return [self._format_vocab_record(record) for record in results]
    
    def delete_vocabulary(self, user_id: str, word: str) -> bool:
        """刪除用戶的單字"""
        try:
            db_path = self._get_db_path()
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            
            c.execute('''DELETE FROM user_vocabulary 
                        WHERE user_id = ? AND word = ?''',
                    (user_id, word))
            
            conn.commit()
            conn.close()
            
            if self.is_cloud:
                self._upload_db()
            return True
        except Exception:
            return False

    def _format_vocab_record(self, record):
        """格式化詞彙記錄"""
        return {
            'word': record[2],
            'definition': record[3],
            'examples': json.loads(record[4]),
            'notes': record[5]
        }
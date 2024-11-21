from datetime import datetime
import sqlite3
import json
from typing import Optional, List

class VocabDatabase:
    def __init__(self, db_path="vocab_learning.db"):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """初始化資料庫表"""
        conn = sqlite3.connect(self.db_path)
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

    def test_connection(self):
        """測試資料庫連接"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.close()
            return True
        except sqlite3.Error:
            return False

    def get_or_create_user(self, username: str) -> str:
        """獲取或創建用戶"""
        conn = sqlite3.connect(self.db_path)
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
        return user_id

    def add_vocabulary(self, user_id: str, word: str, definition: str, 
                    examples: List[str], notes: str = ""):
        """添加新單字到用戶的詞彙表"""
        try:
            conn = sqlite3.connect(self.db_path)
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
            return True
            
        except sqlite3.Error as e:
            raise Exception(f"資料庫錯誤：{str(e)}")
        except Exception as e:
            raise e

    def word_exists(self, user_id: str, word: str) -> bool:
        """檢查單字是否已經存在於用戶的單字本中"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''SELECT COUNT(*) FROM user_vocabulary 
                    WHERE user_id = ? AND word = ?''', (user_id, word))
        
        count = c.fetchone()[0]
        conn.close()
        
        return count > 0

    def get_user_vocabulary(self, user_id: str):
        """獲取用戶的詞彙表"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''SELECT * FROM user_vocabulary 
                    WHERE user_id = ?
                    ORDER BY created_at DESC''', (user_id,))
        
        results = c.fetchall()
        conn.close()
        
        return [self._format_vocab_record(record) for record in results]
    
    def delete_vocabulary(self, user_id: str, word: str) -> bool:
        """刪除用戶的單字"""
        try:
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            
            c.execute('''DELETE FROM user_vocabulary 
                        WHERE user_id = ? AND word = ?''',
                    (user_id, word))
            
            conn.commit()
            conn.close()
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
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
        self.db_path = db_path
        self.bucket_name = bucket_name
        
        if self.is_cloud:
            self.storage_client = storage.Client()
            self.bucket = self.storage_client.bucket(bucket_name)
            self.blob = self.bucket.blob(db_path)
            
        self.init_db()

    def _get_connection(self):
        """獲取數據庫連接"""
        if self.is_cloud:
            # 創建臨時文件
            temp_db = tempfile.NamedTemporaryFile(delete=False)
            temp_path = temp_db.name
            temp_db.close()

            # 如果blob存在，下載到臨時文件
            if self.blob.exists():
                self.blob.download_to_filename(temp_path)
            
            conn = sqlite3.connect(temp_path)
            return conn, temp_path
        else:
            return sqlite3.connect(self.db_path), None

    def _close_connection(self, conn, temp_path=None):
        """關閉連接並處理臨時文件"""
        conn.close()
        
        if self.is_cloud and temp_path:
            # 上傳更新後的數據庫
            self.blob.upload_from_filename(temp_path)
            # 刪除臨時文件
            os.unlink(temp_path)

    def init_db(self):
        """初始化資料庫表"""
        conn, temp_path = self._get_connection()
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
        
        # 聊天會話表
        c.execute('''CREATE TABLE IF NOT EXISTS chat_sessions
                    (chat_id TEXT PRIMARY KEY,
                     user_id TEXT,
                     name TEXT,
                     created_at TIMESTAMP,
                     FOREIGN KEY (user_id) REFERENCES users(user_id))''')
        
        # 聊天消息表
        c.execute('''CREATE TABLE IF NOT EXISTS chat_messages
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     chat_id TEXT,
                     role TEXT,
                     content TEXT,
                     created_at TIMESTAMP,
                     FOREIGN KEY (chat_id) REFERENCES chat_sessions(chat_id))''')
        
        conn.commit()
        self._close_connection(conn, temp_path)

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
        conn, temp_path = self._get_connection()
        c = conn.cursor()
        
        try:
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
            return user_id
            
        finally:
            self._close_connection(conn, temp_path)

    def add_vocabulary(self, user_id: str, word: str, definition: str, 
                      examples: List[str], notes: str = ""):
        """添加新單字到用戶的詞彙表"""
        conn, temp_path = self._get_connection()
        c = conn.cursor()
        
        try:
            # 檢查單字是否已存在
            c.execute('''SELECT COUNT(*) FROM user_vocabulary 
                        WHERE user_id = ? AND word = ?''', (user_id, word))
            
            if c.fetchone()[0] > 0:
                raise ValueError(f"單字 '{word}' 已經存在於您的單字本中")
            
            now = datetime.now()
            c.execute('''INSERT INTO user_vocabulary 
                        (user_id, word, definition, examples, notes, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)''',
                     (user_id, word, definition, json.dumps(examples), notes, now))
            
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            raise e
            
        finally:
            self._close_connection(conn, temp_path)

    def get_user_vocabulary(self, user_id: str):
        """獲取用戶的詞彙表"""
        conn, temp_path = self._get_connection()
        c = conn.cursor()
        
        try:
            c.execute('''SELECT * FROM user_vocabulary 
                        WHERE user_id = ?
                        ORDER BY created_at DESC''', (user_id,))
            
            results = c.fetchall()
            return [self._format_vocab_record(record) for record in results]
            
        finally:
            self._close_connection(conn, temp_path)
    
    def delete_vocabulary(self, user_id: str, word: str) -> bool:
        """刪除用戶的單字"""
        conn, temp_path = self._get_connection()
        c = conn.cursor()
        
        try:
            c.execute('''DELETE FROM user_vocabulary 
                        WHERE user_id = ? AND word = ?''',
                     (user_id, word))
            
            conn.commit()
            return True
            
        except Exception:
            conn.rollback()
            return False
            
        finally:
            self._close_connection(conn, temp_path)

    def _format_vocab_record(self, record):
        """格式化詞彙記錄"""
        return {
            'word': record[2],
            'definition': record[3],
            'examples': json.loads(record[4]),
            'notes': record[5]
        }
    
    def create_chat_session(self, user_id: str, name: str, chat_id: str = None) -> str:
        """創建新的聊天會話"""
        conn, temp_path = self._get_connection()
        c = conn.cursor()
        
        try:
            now = datetime.now()
            # 如果沒有提供 chat_id，則生成新的 UUID
            if chat_id is None:
                chat_id = str(uuid.uuid4())
            
            c.execute('''INSERT INTO chat_sessions (chat_id, user_id, name, created_at)
                        VALUES (?, ?, ?, ?)''', (chat_id, user_id, name, now))
            
            conn.commit()
            return chat_id
        finally:
            self._close_connection(conn, temp_path)

    def get_user_chats(self, user_id: str) -> List[dict]:
        """獲取用戶的所有聊天會話"""
        conn, temp_path = self._get_connection()
        c = conn.cursor()
        
        try:
            c.execute('''SELECT chat_id, name, created_at 
                        FROM chat_sessions 
                        WHERE user_id = ?
                        ORDER BY created_at DESC''', (user_id,))
            
            chats = []
            for row in c.fetchall():
                chat_id, name, created_at = row
                chats.append({
                    "id": chat_id,  # 這裡返回 UUID 格式的 chat_id
                    "name": name,
                    "created_at": created_at
                })
            return chats
        finally:
            self._close_connection(conn, temp_path)

    def add_chat_message(self, chat_id: str, role: str, content: str):
        """添加聊天消息"""
        conn, temp_path = self._get_connection()
        c = conn.cursor()
        
        try:
            now = datetime.now()
            c.execute('''INSERT INTO chat_messages (chat_id, role, content, created_at)
                        VALUES (?, ?, ?, ?)''', (chat_id, role, content, now))
            conn.commit()
        finally:
            self._close_connection(conn, temp_path)

    def get_chat_messages(self, chat_id: str) -> List[dict]:
        """獲取聊天會話的所有消息"""
        conn, temp_path = self._get_connection()
        c = conn.cursor()
        
        try:
            c.execute('''SELECT role, content, created_at 
                        FROM chat_messages 
                        WHERE chat_id = ?
                        ORDER BY created_at ASC''', (chat_id,))
            
            messages = []
            for row in c.fetchall():
                role, content, created_at = row
                messages.append({
                    "role": role,
                    "content": content,
                    "created_at": created_at
                })
            return messages
        finally:
            self._close_connection(conn, temp_path)

    def delete_chat_session(self, chat_id: str) -> bool:
        """刪除聊天會話及其所有消息"""
        conn, temp_path = self._get_connection()
        c = conn.cursor()
        
        try:
            # 首先刪除所有相關的消息
            c.execute('DELETE FROM chat_messages WHERE chat_id = ?', (chat_id,))
            # 然後刪除會話
            c.execute('DELETE FROM chat_sessions WHERE chat_id = ?', (chat_id,))
            
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            self._close_connection(conn, temp_path)

    def update_chat_name(self, chat_id: str, new_name: str) -> bool:
        """更新聊天會話名稱"""
        conn, temp_path = self._get_connection()
        c = conn.cursor()
        
        try:
            c.execute('''UPDATE chat_sessions 
                        SET name = ?
                        WHERE chat_id = ?''', (new_name, chat_id))
            
            conn.commit()
            return True
        except Exception:
            conn.rollback()
            return False
        finally:
            self._close_connection(conn, temp_path)
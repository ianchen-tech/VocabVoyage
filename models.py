import firebase_admin
from firebase_admin import credentials, db
from datetime import datetime
import json
from typing import List, Optional
import os
from dotenv import load_dotenv

load_dotenv()

class VocabDatabase:
    def __init__(self):
        # 初始化 Firebase
        if not firebase_admin._apps:
            # 使用環境變數或服務帳戶金鑰檔案
            if os.getenv('FIREBASE_CREDENTIALS'):
                cred = credentials.Certificate(json.loads(os.getenv('FIREBASE_CREDENTIALS')))
            else:
                cred = credentials.Certificate('FirebaseKey.json')
                
            firebase_admin.initialize_app(cred, {
                'databaseURL': os.getenv('FIREBASE_DATABASE_URL')
            })
        
        self.db = db.reference()

    def get_or_create_user(self, username: str) -> str:
        """獲取或創建用戶"""
        users_ref = self.db.child('users')
        # 查找是否已存在該用戶
        existing_users = users_ref.order_by_child('username').equal_to(username).get()
        
        if existing_users:
            # 返回現有用戶的 ID
            return list(existing_users.keys())[0]
        else:
            # 創建新用戶
            new_user_ref = users_ref.push()
            new_user_ref.set({
                'username': username,
                'created_at': str(datetime.now())
            })
            return new_user_ref.key

    def add_vocabulary(self, user_id: str, word: str, definition: str, 
                      examples: List[str], notes: str = ""):
        """添加新單字到用戶的詞彙表"""
        vocab_ref = self.db.child('vocabulary').child(user_id)
        
        # 檢查單字是否已存在
        existing_vocab = vocab_ref.order_by_child('word').equal_to(word).get()
        if existing_vocab:
            raise ValueError(f"單字 '{word}' 已經存在於您的單字本中")
        
        # 添加新單字
        new_vocab = {
            'word': word,
            'definition': definition,
            'examples': examples,
            'notes': notes,
            'created_at': str(datetime.now())
        }
        vocab_ref.push().set(new_vocab)
        return True

    def get_user_vocabulary(self, user_id: str):
        """獲取用戶的詞彙表"""
        vocab_ref = self.db.child('vocabulary').child(user_id).get()
        if not vocab_ref:
            return []
        
        vocab_list = []
        for key, value in vocab_ref.items():
            vocab_list.append({
                'word': value['word'],
                'definition': value['definition'],
                'examples': value['examples'],
                'notes': value['notes']
            })
        return sorted(vocab_list, key=lambda x: x['word'])

    def delete_vocabulary(self, user_id: str, word: str) -> bool:
        """刪除用戶的單字"""
        vocab_ref = self.db.child('vocabulary').child(user_id)
        vocab_items = vocab_ref.order_by_child('word').equal_to(word).get()
        
        if vocab_items:
            for key in vocab_items.keys():
                vocab_ref.child(key).delete()
            return True
        return False

    def create_chat_session(self, user_id: str, name: str, chat_id: str = None) -> str:
        """創建新的聊天會話"""
        chats_ref = self.db.child('chats').child(user_id)
        new_chat = {
            'name': name,
            'created_at': str(datetime.now())
        }
        
        if chat_id:
            chats_ref.child(chat_id).set(new_chat)
            return chat_id
        else:
            new_chat_ref = chats_ref.push()
            new_chat_ref.set(new_chat)
            return new_chat_ref.key

    def get_user_chats(self, user_id: str) -> List[dict]:
        """獲取用戶的所有聊天會話"""
        chats_ref = self.db.child('chats').child(user_id).get()
        if not chats_ref:
            return []
        
        chats = []
        for chat_id, chat_data in chats_ref.items():
            chats.append({
                'id': chat_id,
                'name': chat_data['name'],
                'created_at': chat_data['created_at']
            })
        return sorted(chats, key=lambda x: x['created_at'], reverse=True)

    def add_chat_message(self, chat_id: str, role: str, content: str):
        """添加聊天消息"""
        messages_ref = self.db.child('messages').child(chat_id)
        new_message = {
            'role': role,
            'content': content,
            'created_at': str(datetime.now())
        }
        messages_ref.push().set(new_message)

    def get_chat_messages(self, chat_id: str) -> List[dict]:
        """獲取聊天會話的所有消息"""
        messages_ref = self.db.child('messages').child(chat_id).get()
        if not messages_ref:
            return []
        
        messages = []
        for msg_data in messages_ref.values():
            messages.append({
                'role': msg_data['role'],
                'content': msg_data['content'],
                'created_at': msg_data['created_at']
            })
        return sorted(messages, key=lambda x: x['created_at'])

    def delete_chat_session(self, chat_id: str) -> bool:
        """刪除聊天會話及其所有消息"""
        try:
            # 刪除所有相關消息
            self.db.child('messages').child(chat_id).delete()
            
            # 找到並刪除聊天會話
            chats = self.db.child('chats').get()
            for user_id, user_chats in chats.items():
                if chat_id in user_chats:
                    self.db.child('chats').child(user_id).child(chat_id).delete()
                    return True
            return False
        except Exception:
            return False

    def update_chat_name(self, chat_id: str, new_name: str) -> bool:
        """更新聊天會話名稱"""
        try:
            # 找到並更新聊天名稱
            chats = self.db.child('chats').get()
            for user_id, user_chats in chats.items():
                if chat_id in user_chats:
                    chat_ref = self.db.child('chats').child(user_id).child(chat_id)
                    chat_data = chat_ref.get()
                    chat_data['name'] = new_name
                    chat_ref.update(chat_data)
                    return True
            return False
        except Exception:
            return False
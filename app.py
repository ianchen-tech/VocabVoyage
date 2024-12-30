import streamlit as st
from graph import process_vocab_query, generate_workflow_graph
from models import VocabDatabase
from dotenv import load_dotenv
import uuid

load_dotenv()

def parse_vocab_response(response: str) -> dict:
    """解析工具回應的內容,區分是否為結構化單字資訊"""
    try:
        lines = response.split('\n')
        vocab_info = {
            "is_word": False,  # 預設為非結構化單字
            "word": None,
            "definition": None,
            "examples": [],
            "part_of_speech": None,
            "related_words": None,
            "tips": None,
            "content": response  # 保存原始回應
        }
        
        # 檢查是否包含結構化單字資訊的關鍵標記
        if "單字：" in response and "定義：" in response:
            vocab_info["is_word"] = True
            
            for line in lines:
                line = line.strip()
                if not line or line == "---":
                    continue
                    
                if line.startswith("單字："):
                    vocab_info["word"] = line.replace("單字：", "").strip()
                elif line.startswith("詞性："):
                    vocab_info["part_of_speech"] = line.replace("詞性：", "").strip()
                elif line.startswith("定義："):
                    vocab_info["definition"] = line.replace("定義：", "").strip()
                elif line.startswith("相關詞彙："):
                    vocab_info["related_words"] = line.replace("相關詞彙：", "").strip()
                elif line.startswith("使用建議："):
                    vocab_info["tips"] = line.replace("使用建議：", "").strip()
                elif line.startswith("-> "):
                    example = line.replace("-> ", "").strip()
                    vocab_info["examples"].append(example)
                elif line.startswith("   (中文翻譯：") and line.endswith(")"):
                    if vocab_info["examples"]:
                        translation = line.replace("   (中文翻譯：", "").rstrip(")")
                        last_example = vocab_info["examples"][-1]
                        vocab_info["examples"][-1] = f"{last_example}\n{translation}"
                        
        return vocab_info
        
    except Exception as e:
        print(f"解析錯誤：{str(e)}")
        return {
            "is_word": False,
            "content": response
        }

# 初始化資料庫
db = VocabDatabase()

st.set_page_config(
    page_title="VocabVoyage",
    page_icon="🎓",
    layout="wide"
)

# 簡化的用戶管理
if 'username' not in st.session_state:
    st.session_state.username = None
    st.session_state.user_id = None

# 登入界面
if not st.session_state.username:
    st.title("Welcome to VocabVoyage")
    with st.form("login_form"):
        username = st.text_input("請輸入你的名字開始學習：")
        submit_button = st.form_submit_button("開始學習")
        if submit_button:
            if username:
                st.session_state.username = username
                st.session_state.user_id = db.get_or_create_user(username)
                st.rerun()
            else:
                st.error("請輸入名字")
else:
    # 側邊欄導航
    with st.sidebar:
        st.title(f"Hi! {st.session_state.username}~ 👋")
        app_mode = st.selectbox(
            "選擇功能",
            ["聊天學習", "我的單字本", "使用指南", "系統架構"]
        )

        if st.button("登出"):
            # 清除session state中的使用者資訊
            st.session_state.username = None
            st.session_state.user_id = None
            if "messages" in st.session_state:
                del st.session_state.messages
            if "current_chat_id" in st.session_state:
                del st.session_state.current_chat_id
            st.rerun()

    # 主要功能區域
    if app_mode == "聊天學習":
        st.title("英文學習助手")
        
        # 初始化聊天管理
        if "current_chat_id" not in st.session_state:
            # 獲取用戶的聊天列表
            user_chats = db.get_user_chats(st.session_state.user_id)
            if not user_chats:
                # 如果用戶沒有聊天記錄，創建第一個聊天
                chat_id = str(uuid.uuid4())  # 使用 UUID 生成唯一ID
                db.create_chat_session(st.session_state.user_id, "聊天 1", chat_id)
                st.session_state.current_chat_id = chat_id
            else:
                # 使用最新的聊天作為當前聊天
                st.session_state.current_chat_id = user_chats[0]["id"]
            
        # 在側邊欄添加聊天管理
        with st.sidebar:
            # 加入空白間距
            st.markdown("----", unsafe_allow_html=True)

            # 聊天管理
            st.markdown("### 聊天管理")
            
            # 獲取用戶的所有聊天
            user_chats = db.get_user_chats(st.session_state.user_id)
            
            # 下拉式選單選擇聊天
            chat_options = {chat["id"]: chat["name"] for chat in user_chats}
            chat_ids = list(chat_options.keys())
            try:
                current_index = chat_ids.index(st.session_state.current_chat_id)
            except ValueError:
                current_index = 0
                if chat_ids:
                    st.session_state.current_chat_id = chat_ids[0]
            
            if chat_ids:  # 確保有聊天可選
                selected_chat = st.selectbox(
                    "切換聊天",
                    options=chat_ids,
                    format_func=lambda x: chat_options[x],
                    key="chat_selector",
                    index=current_index
                )
                
                # 編輯聊天名稱
                current_chat_name = next((chat["name"] for chat in user_chats if chat["id"] == selected_chat), "")
                new_chat_name = st.text_input(
                    "修改聊天名稱",
                    value=current_chat_name,
                    key=f"edit_name_{selected_chat}"
                )

                # 如果名稱有變更，更新數據庫
                if new_chat_name != current_chat_name:
                    if db.update_chat_name(selected_chat, new_chat_name):
                        st.rerun()
            
            # 新增和刪除按鈕並排
            button_container = st.container()
            with button_container:
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("➕", key="new_chat_button", help="新增聊天"):
                        # 創建新的聊天會話
                        chat_count = len(user_chats)
                        new_chat_name = f"聊天 {chat_count + 1}"
                        new_chat_id = str(uuid.uuid4())  # 使用 UUID 生成唯一ID
                        db.create_chat_session(st.session_state.user_id, new_chat_name, new_chat_id)
                        st.session_state.current_chat_id = new_chat_id
                        st.rerun()
                
                with col2:
                    if st.button("🗑️", key="delete_chat_button", help="刪除目前的聊天"):
                        if db.delete_chat_session(selected_chat):
                            # 如果刪除成功，更新當前聊天ID
                            remaining_chats = db.get_user_chats(st.session_state.user_id)
                            if remaining_chats:
                                st.session_state.current_chat_id = remaining_chats[0]["id"]
                            else:
                                # 如果沒有剩餘的聊天，創建一個新的
                                new_chat_id = str(uuid.uuid4())  # 生成新的 UUID
                                db.create_chat_session(st.session_state.user_id, "聊天 1", new_chat_id)
                                st.session_state.current_chat_id = new_chat_id
                            
                            # 清除相關的 session state 以確保頁面完全重新載入
                            if "chat_selector" in st.session_state:
                                del st.session_state.chat_selector
                            
                            st.rerun()

        # 更新當前聊天
        if "selected_chat" in locals() and selected_chat != st.session_state.current_chat_id:
            st.session_state.current_chat_id = selected_chat
            st.rerun()
        
        # 獲取當前聊天的消息
        current_chat_messages = db.get_chat_messages(st.session_state.current_chat_id)
        
        # 如果是新聊天，顯示歡迎消息
        if not current_chat_messages:
            welcome_msg = """歡迎使用 VocabVoyage！

你可以：
1. 📖 查詢單字的詳細用法
   - "解釋 'sustainability' 的意思"
   - "說明 'blockchain' 怎麼用"
   - "'machine learning' 這個詞組是什麼意思？"
2. 📚 學習特定主題的單字
   - "我想學習飲食美食相關的單字"
   - "教我一些環保議題常用的詞彙"
   - "介紹金融科技領域的重要單字"
3. 📝 進行主題測驗
   - "測驗我的科技英文程度"
   - "出一份關於永續發展的詞彙測驗"
   - "測試我對商業用語的掌握"
4. 💭 提出英文相關協助
   - "幫我寫一篇關於冒險的英文故事"
   - "幫我潤飾這段英文文章"
"""
            db.add_chat_message(st.session_state.current_chat_id, "assistant", welcome_msg)
            current_chat_messages = db.get_chat_messages(st.session_state.current_chat_id)

        # 顯示聊天歷史
        messages_container = st.container()
        with messages_container:
            for message in current_chat_messages:
                with st.chat_message(message["role"]):
                    # 檢查是否為結構化單字資訊
                    if isinstance(message["content"], str) and "單字：" in message["content"] and "定義：" in message["content"]:
                        parsed_response = parse_vocab_response(message["content"])
                        if parsed_response["is_word"]:
                            st.markdown(f"### 📝 {parsed_response['word']}")
                            if parsed_response['part_of_speech']:
                                st.markdown(f"**詞性:** {parsed_response['part_of_speech']}")
                            st.markdown(f"**定義:** {parsed_response['definition']}")
                            
                            if parsed_response['examples']:
                                st.markdown("**例句:**")
                                for example in parsed_response['examples']:
                                    st.markdown(f"- {example}")
                                    
                            if parsed_response['related_words']:
                                st.markdown(f"**相關詞彙:** {parsed_response['related_words']}")
                                
                            if parsed_response['tips']:
                                st.markdown(f"**使用建議:** {parsed_response['tips']}")
                        else:
                            st.markdown(message["content"])
                    else:
                        st.markdown(message["content"])

        # 用戶輸入
        if prompt := st.chat_input("輸入你的問題..."):
            # 生成 thread_id
            current_thread_id = f"{st.session_state.user_id}_{st.session_state.current_chat_id}"
            
            # 添加用戶ID和thread_id到查詢中
            user_query = {
                "messages": [{"role": "user", "content": prompt}],
                "user_id": st.session_state.user_id,
                "thread_id": current_thread_id
            }
            
            # 保存用戶消息
            db.add_chat_message(st.session_state.current_chat_id, "user", prompt)
            
            with st.chat_message("user"):
                st.markdown(prompt)

            # 處理回應
            with st.chat_message("assistant"):
                with st.spinner("撰寫中..."):
                    try:
                        response = process_vocab_query(user_query)
                        parsed_response = parse_vocab_response(response)

                        if parsed_response["is_word"]:
                            # 嘗試保存單字到資料庫
                            try:
                                db.add_vocabulary(
                                    user_id=st.session_state.user_id,
                                    word=parsed_response['word'],
                                    definition=parsed_response['definition'],
                                    examples=parsed_response['examples'] if parsed_response['examples'] else [],
                                    notes=f"`詞性: {parsed_response['part_of_speech'] or ''}`\n" +
                                        f"`相關詞彙: {parsed_response['related_words'] or ''}`\n" +
                                        f"`使用建議: {parsed_response['tips'] or ''}`"
                                )
                                st.success(f"已將 '{parsed_response['word']}' 加入你的單字本！")
                            except ValueError as ve:
                                st.info(str(ve))
                            except Exception as e:
                                st.error(f"保存單字時發生錯誤：{str(e)}")

                            # 顯示結構化的單字資訊
                            st.markdown(f"### 📝 {parsed_response['word']}")
                            if parsed_response['part_of_speech']:
                                st.markdown(f"**詞性:** {parsed_response['part_of_speech']}")
                            st.markdown(f"**定義:** {parsed_response['definition']}")
                            
                            if parsed_response['examples']:
                                st.markdown("**例句:**")
                                for example in parsed_response['examples']:
                                    st.markdown(f"- {example}")
                                    
                            if parsed_response['related_words']:
                                st.markdown(f"**相關詞彙:** {parsed_response['related_words']}")
                                
                            if parsed_response['tips']:
                                st.markdown(f"**使用建議:** {parsed_response['tips']}")

                        else:
                            # 直接顯示非結構化的回應內容
                            st.markdown(parsed_response["content"])
                            
                    except Exception as e:
                        st.error(f"發生錯誤：{str(e)}")
                        
            # 保存助手回應
            db.add_chat_message(st.session_state.current_chat_id, "assistant", response)

    elif app_mode == "我的單字本":
        st.title("📖 我的單字本")
        
        # 獲取用戶的所有單字
        vocab_list = db.get_user_vocabulary(st.session_state.user_id)
        
        if vocab_list:
            for vocab in vocab_list:
                with st.expander(f"📝 {vocab['word']}"):
                    col1, col2 = st.columns([10, 1])
                    
                    with col1:
                        st.write(f"**定義:** {vocab['definition']}")
                        if vocab['examples']:
                            st.write("**例句:**")
                            for example in vocab['examples']:
                                st.write(f"- {example}")
                        if vocab['notes']:
                            st.write(f"**筆記:** {vocab['notes']}")
                    
                    with col2:
                        if st.button("🗑️", key=f"delete_{vocab['word']}", help="刪除這個單字"):
                            if db.delete_vocabulary(st.session_state.user_id, vocab['word']):
                                st.success(f"已刪除 '{vocab['word']}'")
                                st.rerun()
                            else:
                                st.error("刪除失敗")
        else:
            st.info("還沒有儲存的單字。開始聊天學習來添加新單字吧！")

    elif app_mode == "使用指南":
        st.title("💡 使用指南")
        st.markdown("""
        ### 1. 單字查詢 📖
        直接查詢特定單字或片語：
        - `解釋 'sustainability' 的意思`
        - `說明 'blockchain' 怎麼用`
        - `'machine learning' 這個詞組是什麼意思？`

        ### 2. 主題學習 📚
        選擇你感興趣的主題，例如：
        - `我想學習飲食美食相關的單字`
        - `教我一些環保議題常用的詞彙`
        - `介紹金融科技領域的重要單字`
        
        系統會根據主題提供相關的重要詞彙和用法說明。
        
        ### 3. 主題測驗 📝
        測試特定領域的詞彙掌握程度：
        - `測驗我的科技英文程度`
        - `出一份關於永續發展的詞彙測驗`
        - `測試我對商業用語的掌握`
                    
        ### 4. 英文相關協助 💭
        獲得與英文相關的協助：
        - `幫我寫一篇關於[主題]的英文短文`
        - `請幫我翻譯這段中文到英文：[文字內容]`
        - `請幫我潤飾這段英文：[英文內容]`
        - `我該如何學好英文？`
        - `寫一篇旅遊景點的英文介紹`
        
        ### 5. 單字本複習 🔄
        在「我的單字本」中查看和複習已儲存的單字：
        - `查看已儲存單字的定義和例句`
        - `複習個人收藏的重要詞彙`
        - `管理和刪除已儲存的單字`
        """, unsafe_allow_html=True)

    elif app_mode == "系統架構":
        st.title("⚙️ 系統架構")
        st.markdown("""
        ### VocabVoyage 使用了以下技術：
        -----
        1. LangGraph 工作流程
           - 智能識別用戶意圖
           - 動態生成學習內容
        -----
        2. RAG (Retrieval-Augmented Generation) 
           - 從向量資料庫檢索相關單字資訊
           - 生成個性化的學習內容
        -----
        3. 智能學習特色
           - 自動生成相關的練習題
           - 智能詞彙關聯分析
        -----
        LangGraph 流程圖
        """)
        # 顯示系統架構圖
        dot = generate_workflow_graph()
        st.graphviz_chart(dot)
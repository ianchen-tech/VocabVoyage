from typing import TypedDict, Annotated, Sequence, Literal
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_chroma import Chroma
from langchain.tools import Tool
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.output_parsers import StrOutputParser
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
import graphviz
import pprint
from models import VocabDatabase

# 初始化資料庫
db = VocabDatabase()

def get_recent_chat_history(chat_id: str) -> list[BaseMessage]:
    """從資料庫獲取最近的聊天記錄"""
    messages = db.get_chat_messages(chat_id)
    if not messages:
        return []
    
    # 只取最近的兩輪對話（2個user和2個assistant）
    recent_messages = []
    user_count = 0
    assistant_count = 0
    
    # 從最新的消息開始往前遍歷
    for msg in reversed(messages):
        if msg["role"] == "user" and user_count < 2:
            recent_messages.insert(0, HumanMessage(content=msg["content"]))
            user_count += 1
        elif msg["role"] == "assistant" and assistant_count < 2:
            recent_messages.insert(0, AIMessage(content=msg["content"]))
            assistant_count += 1
            
        if user_count >= 2 and assistant_count >= 2:
            break
            
    return recent_messages

# 定義狀態類型
class VocabState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    context: dict
    user_id: str

# 提示詞
SYSTEM_PROMPTS = {
    "search": """
你是一個專業的英語教師。請使用繁體中文提供這個單字的詳細資訊，格式如下：
---
單字：[英文單字]
詞性：[以繁體中文說明詞性]
定義：[繁體中文定義]
例句：
-> [英文例句1]
    (中文翻譯：[繁體中文翻譯])
-> [英文例句2]
    (中文翻譯：[繁體中文翻譯])
相關詞彙：[相關英文詞彙（其詞性及繁體中文解釋）、相關英文詞彙（其詞性及繁體中文解釋）...](接續在後面就好，不要條列！)
使用建議：[單字使用建議的繁體中文說明]
---
請確保回應嚴格遵循以上格式，所有解釋都使用繁體中文。
""",

    "category": """
根據檢索到的資料列出相關單字。
檢索到的資料：{context}

請列出其中隨機30個單字或片語，使用繁體中文解釋，格式如下：

【類別名稱】相關單字或片語：

1. [英文單字/片語1]
- 定義：[繁體中文定義]
- 詞性：[詞性]
- 使用：[單字使用建議的說明(繁體中文)]
- 例句：[英文例句]
       (中文翻譯：[繁體中文翻譯])

2. [英文單字/片語2]
...（依此類推）
""",

    "quiz": """
你是一個專業的英語教師。請根據提供的單字資訊生成一個完整的測驗。
所有說明和解釋都需使用繁體中文。

以下是相關的單字資訊：
{context}

===== 測驗說明 =====
本測驗共分為三個部分，目的在於全面性地測試您對單字的掌握程度：
1. 選擇題：測試單字的定義和用法理解
2. 填空題：測試單字在語境中的正確使用
3. 配對題：測試單字與其定義的對應關係

===== 測驗開始 =====

【第一部分：選擇題】(共5題)
說明：每題皆有四個選項，請選出最適當的答案
--------------------
1. [題目內容(中文)] \n
   A) [選項A(英文)]
   B) [選項B(英文)]
   C) [選項C(英文)]
   D) [選項D(英文)]

2. [依此格式撰寫其餘題目...]

【第二部分：填空題】(共5題)
說明：請將適當的單字填入句子空格中，單字需做適當的語態變化
--------------------
1. The company needs to ________ its marketing strategy to adapt to the changing market.   ----- (提示：調整/修改)

2. [依此格式撰寫其餘題目...]

【第三部分：配對題】(共5題)
說明：請將上方的單字與下方的解釋配對，在橫線上填入對應的選項代號
--------------------
單字：
1. ________ innovation
2. ________ sustainable
3. ________ implement
4. ________ strategy
5. ________ efficiency \n
解釋：
A) 可持續發展的
B) 創新
C) 執行
D) 策略
E) 效率

===== 答案與解釋 =====

【選擇題答案】
1. [正確選項] \n
解釋：[詳細說明為什麼這是正確答案，並解釋其他選項為何不適當]

2. [依此格式提供其餘答案...]

【填空題答案】
1. adjust/modify \n
解釋：[說明為什麼這個單字最適合此語境，並解釋單字的用法和其他可能的同義詞]

2. [依此格式提供其餘答案...]

【配對題答案】
1. B  2. A  3. C  4. D  5. E \n
解釋：
- innovation (B)：[詳細解釋單字意義和用法]
- sustainable (A)：[詳細解釋單字意義和用法]
[依此格式解釋其餘配對]

===== 總結建議 ===== \n
[針對這些單字的學習提供具體建議和記憶方法]

----
答案與解釋請完整、詳細、友善、像老師。
請把格式排版好看。是 markdown 格式。
""",

    "other": """
你是一個友善的英語學習助手。請使用繁體中文回應。

如果用戶的問題與英語學習無關，請友善地引導他們詢問英語相關的問題。
你可以提供以下建議：
1. 查詢單字或片語的意思和用法
2. 瀏覽特定主題領域的詞彙（如：商業、科技、醫療等）
3. 進行特定主題的詞彙測驗

如果用戶的問題確實與英語學習有關，則直接回答他們的問題。要求短篇英文小文章或翻譯是可以的。

請使用友善且鼓勵的語氣，確保說明的部分都使用繁體中文。
"""
}

def agent(state: VocabState):
    """
    代理節點：決定是否使用工具或直接生成回應
    """
    print(" *** 調用代理 *** ")
    messages = state["messages"]

    system_message = """你是一個英語學習助手的路由器。
你的唯一任務是決定是否使用提供的工具來回答用戶的問題。
- 如果問題需要用工具回答，請使用適當的工具
- 如果問題不需要工具（比如一般英語學習建議或非英語相關問題），請回覆 "DIRECT_RESPONSE"
- 注意不要輕易的使用category_vocabulary_list跟vocabulary_quiz_generator這兩個工具，要確定你真的必須使用它們再使用
不要直接回答用戶的問題，只需決定使用工具或返回標記。"""
    messages = [HumanMessage(content=system_message)] + messages

    model = ChatOpenAI(temperature=0.7, model="gpt-4o-mini")
    model = model.bind_tools(tools)
    response = model.invoke(messages)
    return {
        "messages": [response],
        "context": state["context"],
        "user_id": state["user_id"]
    }

def generate_response(state: VocabState):
    """回應生成節點：生成最終回應"""
    print(" *** 生成回應 *** ")
    messages = state["messages"]
    last_message = messages[-1]
    
    # 處理工具回覆
    if isinstance(last_message, ToolMessage):
        return {
            "messages": [last_message],
            "context": state["context"],
            "user_id": state["user_id"]
        }
    
    # 處理其他情況
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

    # 將聊天歷史轉換為格式化的字符串
    chat_history = []
    for msg in messages[:-2]:  # 除了最新消息外的所有歷史
        role = "用戶" if isinstance(msg, HumanMessage) else "助手"
        chat_history.append(f"{role}: {msg.content}")
    formatted_history = "\n".join(chat_history)
    
    current_question = messages[-2].content  # 最新的問題

    prompt = PromptTemplate(
        template=SYSTEM_PROMPTS["other"] + "\n\n=== 聊天歷史 ===\n{chat_history}\n\n=== 最新問題 ===\n{query}",
        input_variables=["chat_history", "query"]
    )
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({
        "chat_history": formatted_history,
        "query": current_question
    })
    
    return {
        "messages": [AIMessage(content=response)],
        "context": state["context"],
        "user_id": state["user_id"]
    }

def setup_rag():
    """設置 RAG 相關組件"""
    print(" *** 調用 RAG *** ")
    vectorstore = Chroma(
        persist_directory="./chroma_db",
        embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
        collection_name="vocabulary_v1"
    )
    return vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": 1}
    )

def search_vocabulary(query: str) -> str:
    """處理單字查詢"""
    print(" *** 調用單字查詢 *** ")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    prompt = PromptTemplate(
        template=SYSTEM_PROMPTS["search"] + "\n\n查詢單字: {query}",
        input_variables=["query"]
    )
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"query": query})
    return response

def get_category_vocabulary(category: str) -> str:
    """處理類別查詢"""
    print(" *** 調用類別查詢 *** ")
    retriever = setup_rag()
    docs = retriever.invoke(category)
    context = "\n".join(doc.page_content for doc in docs)
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    prompt = PromptTemplate(
        template=SYSTEM_PROMPTS["category"],
        input_variables=["context"]
    )
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"context": context})
    return response

def generate_quiz(category: str) -> str:
    """生成類別測驗"""
    print(" *** 調用生成類別測驗 *** ")
    retriever = setup_rag()
    docs = retriever.invoke(category)
    context = "\n".join(doc.page_content for doc in docs)
    
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)
    prompt = PromptTemplate(
        template=SYSTEM_PROMPTS["quiz"],
        input_variables=["context"]
    )
    chain = prompt | llm | StrOutputParser()
    response = chain.invoke({"context": context})
    return response

# 創建工具
tools = [
    Tool(
        name="search_vocabulary_details",
        description="""
用於查詢單個英文單字或片語的詳細資訊。適用情況：
1. 想知道某個英文單字的中文意思
2. 需要查詢單字的詳細用法和例句
3. 想了解單字的相關詞彙
使用方式：輸入「查詢單字 [你想查的單字]」或「解釋單字 [你想查的單字]」
例如：
- 查詢單字 resilient
- 解釋單字 innovation
- artificial 是什麼
""",
        func=search_vocabulary,
        return_direct=True
    ),
    Tool(
        name="category_vocabulary_list",
        description="""
用於獲取特定主題或領域的相關英文單字列表(只問或只需要一個單字則不會用到)。
適用情況：
1. 想學習特定領域的多個專業詞彙
2. 需要某個主題的相關單字
3. 想擴充特定場景的詞彙量
支援的類別包括但不限於：
- 商業/金融 (Business/Finance)
- 科技/IT (Technology/IT)
- 醫療/健康 (Medical/Health)
- 教育/學術 (Education/Academic)
- 環境/生態 (Environment/Ecology)
使用方式：輸入「列出 [類別] 相關單字」或「我想學習 [領域] 的單字」
例如：
- 列出商業相關單字
- 我想學習醫療領域的詞彙
- 給我一些科技方面的專業用語
""",
        func=get_category_vocabulary,
        return_direct=True
    ),
    Tool(
        name="vocabulary_quiz_generator",
        description="""
用於生成特定主題的英文單字測驗(只問或只需要一個單字則不會用到)。
適用情況：
1. 想測試特定領域的詞彙掌握程度
2. 需要練習題進行自我評估
3. 想以測驗方式學習新單字
使用方式：輸入「生成 [主題] 測驗」或「我要做 [領域] 的單字測驗」
例如：
- 生成商業英文測驗
- 我要做科技詞彙的測驗
- 幫我出一份環保主題的單字測驗
""",
        func=generate_quiz,
        return_direct=True
    )
]

def create_vocab_chain():
    """創建主要工作流程"""
    # 創建工具節點
    tool_node = ToolNode(tools=tools)
    
    # 建立工作流程圖
    workflow = StateGraph(VocabState)
    
    # 添加節點
    workflow.add_node("agent", agent)
    workflow.add_node("tools", tool_node)
    workflow.add_node("generate", generate_response)
    
    # 添加邊
    workflow.add_edge(START, "agent")
    
    # 從代理到工具或生成的條件邊
    workflow.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            END: "generate",
        }
    )
    
    # 工具節點到生成節點
    workflow.add_edge("tools", "generate")
    
    workflow.add_edge("generate", END)

    # 編譯時加入 checkpointer
    return workflow.compile()

def process_vocab_query(query_data: dict):
    """處理查詢請求"""
    app = create_vocab_chain()
    chat_id = query_data["thread_id"]

    # 獲取最近的聊天記錄
    previous_messages = get_recent_chat_history(chat_id)
    
    # 將新消息添加到歷史記錄中
    input_messages = previous_messages + query_data["messages"]

    input_data = {
        "messages": input_messages,
        "context": {},
        "user_id": query_data["user_id"]
    }

    # 使用準備好的輸入數據調用 stream
    for output in app.stream(input_data):
        for key, value in output.items():
            # if "messages" in value:
            #     value["messages"][-1].pretty_print()
            #     print('================================================================================')
            print()
    
    return value['messages'][-1].content

def generate_workflow_graph():
    """生成工作流程圖"""
    dot = graphviz.Digraph(comment='Vocabulary Learning Workflow')
    dot.attr(rankdir='TB')
    
    # 節點
    dot.node('START', 'Start')
    dot.node('agent', 'Agent\n(Decision Making)')
    dot.node('tools', 'Tools\n(Search/Category/Quiz)')
    dot.node('generate', 'Generate Response')
    dot.node('END', 'End')
    
    # 邊
    dot.edge('START', 'agent')
    dot.edge('agent', 'tools', 'needs tools')
    dot.edge('agent', 'generate', 'direct response')
    dot.edge('tools', 'generate', 'complete')
    dot.edge('generate', 'END')
    
    return dot

if __name__ == "__main__":
    # 測試案例
    test_cases = [
        # {
        #     "name": "Word Search",
        #     "query": {
        #         "messages": [HumanMessage(content="resilient 是什麼意思")],
        #         "user_id": "test_user_1"
        #     }
        # },
        # {
        #     "name": "Category Search",
        #     "query": {
        #         "messages": [HumanMessage(content="想了解商業相關單字")],
        #         "user_id": "test_user_1"
        #     }
        # },
        # {
        #     "name": "Quiz Generation",
        #     "query": {
        #         "messages": [HumanMessage(content="我想測驗科技相關的單字")],
        #         "user_id": "test_user_1"
        #     }
        # },
        # {
        #     "name": "General Conversation",
        #     "query": {
        #         "messages": [HumanMessage(content="我想學習英文，但不知道從何開始？")],
        #         "user_id": "test_user_1"
        #     }
        # },
        # {
        #     "name": "Non-English Learning Question",
        #     "query": {
        #         "messages": [HumanMessage(content="今天天氣如何？")],
        #         "user_id": "test_user_1"
        #     }
        # }
        {
            "name": "General Conversation",
            "query": {
                "messages": [HumanMessage(content="給我一個高深的單字，一個就好")],
                "user_id": "test",
                "thread_id": "3dc6d9cd-95ef-44fc-aa30-935f6592c648"
            }
        },
        {
            "name": "Follow-up Question", 
            "query": {
                "messages": [HumanMessage(content="針對這個單字給我一個例句")],
                "user_id": "test",
                "thread_id": "3dc6d9cd-95ef-44fc-aa30-935f6592c648"
            }
        }
    ]

    for test in test_cases:
        print(f"\n=== Test Case: {test['name']} ===")
        response = process_vocab_query(test["query"])
        db.add_chat_message('3dc6d9cd-95ef-44fc-aa30-935f6592c648', "assistant", response)
        print("\nResponse:", response)
        

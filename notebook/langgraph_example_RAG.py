# ============================================================================ 建資料
# from langchain_chroma import Chroma
# from langchain_openai import OpenAIEmbeddings
# from langchain_community.document_loaders import WebBaseLoader
# from langchain_text_splitters import RecursiveCharacterTextSplitter

# urls = [
#     "https://lilianweng.github.io/posts/2023-06-23-agent/",
#     "https://lilianweng.github.io/posts/2023-03-15-prompt-engineering/",
#     "https://lilianweng.github.io/posts/2023-10-25-adv-attack-llm/",
# ]

# docs = [WebBaseLoader(url).load() for url in urls]
# docs_list = [item for sublist in docs for item in sublist]

# text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
#     chunk_size=100, chunk_overlap=50
# )
# doc_splits = text_splitter.split_documents(docs_list)

# # Add to vectorDB
# vectorstore = Chroma.from_documents(
#     documents=doc_splits,
#     collection_name="rag-example",
#     embedding=OpenAIEmbeddings(model="text-embedding-3-small"),
#     persist_directory="./chroma_db"
# )

# ============================================================================ 查資料
# import chromadb

# client = chromadb.PersistentClient(path="./chroma_db")
# collection = client.get_collection("rag-example")

# results = collection.get()

# results_ = collection.peek()
# print(results_)

# doc_count = collection.count()
# print(f"Number of documents in the collection: {doc_count}")

# ============================================================================ 用資料
from langchain_chroma import Chroma
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.tools.retriever import create_retriever_tool
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from typing import Annotated, Literal, Sequence
from langchain import hub
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field
from langgraph.prebuilt import tools_condition
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import ToolNode
import pprint

# 載入數據庫
vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=OpenAIEmbeddings(model="text-embedding-3-small"),
    collection_name="rag-example"
)
# 創建檢索器
retriever = vectorstore.as_retriever()

# 創建工具
retriever_tool = create_retriever_tool(
    retriever=retriever,
    name="retrieve_blog_posts",
    description="搜索並返回有關 Lilian Weng 在 LLM 代理、提示工程和對 LLM 的對抗性攻擊的博客文章的信息。",
)
tools = [retriever_tool]

# 定義狀態
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]

# 定義節點
def grade_documents(state) -> Literal["generate", "rewrite"]:
    """
    判斷檢索到的文檔是否與問題相關。

    參數:
        state (messages): 當前狀態

    返回:
        str: 判斷文檔是否相關的決定
    """

    print(" *** 檢查相關性 *** ")

    # 數據模型
    class grade(BaseModel):
        """相關性檢查的二元評分。"""

        binary_score: str = Field(description="相關性評分 'yes' 或 'no'")

    # LLM
    model = ChatOpenAI(temperature=0, model="gpt-4o-mini", streaming=True)

    # 帶有工具和驗證的 LLM
    llm_with_tool = model.with_structured_output(grade)

    # 提示
    prompt = PromptTemplate(
        template="""你是一個評分員，評估檢索到的文檔與用戶問題的相關性。\n 
        這是檢索到的文檔：\n\n {context} \n\n
        這是用戶問題：{question} \n
        如果文檔包含與用戶問題相關的關鍵詞或語義含義，將其評為相關。\n
        給出二元評分 'yes' 或 'no' 來表示文檔是否與問題相關。""",
        input_variables=["context", "question"],
    )

    # 鏈
    chain = prompt | llm_with_tool

    messages = state["messages"]
    last_message = messages[-1]

    question = messages[0].content
    docs = last_message.content

    scored_result = chain.invoke({"question": question, "context": docs})

    score = scored_result.binary_score

    if score == "yes":
        print(" *** 決定：文檔相關 *** ")
        return "generate"

    else:
        print(" *** 決定：文檔不相關 *** ")
        print(score)
        return "rewrite"

def agent(state):
    """
    調用代理模型根據當前狀態生成回應。給定問題後，
    它將決定使用檢索工具進行檢索，或者直接結束。

    參數:
        state (messages): 當前狀態

    返回:
        dict: 更新後的狀態，代理回應已附加到消息中
    """
    print(" *** 調用代理 *** ")
    messages = state["messages"]
    model = ChatOpenAI(temperature=0, streaming=True, model="gpt-4o-mini")
    model = model.bind_tools(tools)
    response = model.invoke(messages)
    # 我們返回一個列表，因為這將被添加到現有列表中
    return {"messages": [response]}

def rewrite(state):
    """
    轉換查詢以產生更好的問題。

    參數:
        state (messages): 當前狀態

    返回:
        dict: 更新後的狀態，包含重新表述的問題
    """

    print(" *** 轉換查詢 *** ")
    messages = state["messages"]
    question = messages[0].content

    msg = [
        HumanMessage(
            content=f""" \n 
    查看輸入並嘗試推理潛在的語義意圖/含義。\n 
    這是初始問題：
    \n  ***  *** - \n
    {question} 
    \n  ***  *** - \n
    制定一個改進的問題：""",
        )
    ]

    # 評分器
    model = ChatOpenAI(temperature=0, model="gpt-4o-mini", streaming=True)
    response = model.invoke(msg)
    return {"messages": [response]}

def generate(state):
    """
    生成答案

    參數:
        state (messages): 當前狀態

    返回:
         dict: 更新後的狀態，包含重新表述的問題
    """
    print(" *** 生成 *** ")
    messages = state["messages"]
    question = messages[0].content
    last_message = messages[-1]

    docs = last_message.content

    # 提示
    prompt = hub.pull("rlm/rag-prompt")

    # LLM
    llm = ChatOpenAI(model_name="gpt-4o-mini", temperature=0, streaming=True)

    # 後處理
    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    # 鏈
    rag_chain = prompt | llm | StrOutputParser()

    # 運行
    response = rag_chain.invoke({"context": docs, "question": question})
    return {"messages": [response]}



# 建立圖形
workflow = StateGraph(AgentState)

# 建立節點
workflow.add_node("agent", agent)  # 代理
retrieve = ToolNode([retriever_tool])
workflow.add_node("retrieve", retrieve)  # 檢索
workflow.add_node("rewrite", rewrite)  # 重寫問題
workflow.add_node("generate", generate)  # 在確認文件相關後生成回應

# 建立邊
workflow.add_edge(START, "agent")
workflow.add_conditional_edges( # 決定是否檢索
    "agent",
    tools_condition, # 評估是否代理
    {
        "tools": "retrieve",
        END: END,
    },
)
workflow.add_conditional_edges( # 決定是否重寫
    "retrieve",
    grade_documents, # 評估檢索品質
)
workflow.add_edge("generate", END)
workflow.add_edge("rewrite", "agent")

# 編譯
graph = workflow.compile()

# from IPython.display import Image, display
# display(Image(graph.get_graph(xray=True).draw_mermaid_png()))

inputs = {
    "messages": [
        ("user", "Lilian Weng 說了什麼? 使用繁體中文回答"),
    ]
}
for output in graph.stream(inputs):
    for key, value in output.items():
        pprint.pprint(f"Output from node '{key}':")
        pprint.pprint(" ===== ")
        pprint.pprint(value, indent=2, width=80, depth=None)
    pprint.pprint(" ========== ")
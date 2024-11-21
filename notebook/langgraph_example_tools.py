from typing import Annotated, Literal
import re
from datetime import datetime

from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage, ToolMessage, HumanMessage
from langchain.tools import Tool
from pydantic import BaseModel
from typing_extensions import TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

# 定義狀態類型
class State(TypedDict):
    messages: Annotated[list, add_messages]
    ask_human: bool

# 定義請求人工協助的模型
class RequestAssistance(BaseModel):
    """請求專家協助。當無法直接回答或需要超出權限的支援時使用。"""
    request: str

# 定義數學計算工具函數
def math_calculator(expression: str) -> str:
    """
    執行基本的數學計算。
    支援加法(+)、減法(-)、乘法(*)和除法(/)。
    """
    try:
        # 使用正則表達式來提取數字和運算符
        parts = re.findall(r'(\d+(?:\.\d+)?|\+|\-|\*|\/)', expression)
        if len(parts) < 3:
            return "錯誤：表達式格式不正確。請提供至少兩個數字和一個運算符。"
        
        result = float(parts[0])
        for i in range(1, len(parts), 2):
            operator = parts[i]
            operand = float(parts[i+1])
            if operator == '+':
                result += operand
            elif operator == '-':
                result -= operand
            elif operator == '*':
                result *= operand
            elif operator == '/':
                if operand == 0:
                    return "錯誤：除數不能為零。"
                result /= operand
        
        return f"計算結果：{result}"
    except Exception as e:
        return f"計算錯誤：{str(e)}"

# 定義日期轉換工具函數
def date_converter(date_string: str, output_format: str = "%Y年%m月%d日") -> str:
    """
    將日期字符串轉換為指定格式。
    輸入格式應為 YYYY-MM-DD。
    """
    try:
        date_obj = datetime.strptime(date_string, "%Y-%m-%d")
        return date_obj.strftime(output_format)
    except ValueError:
        return "錯誤：日期格式不正確。請使用 YYYY-MM-DD 格式。"

# 創建數學計算工具
math_tool = Tool(
    name="math_calculator",
    description="執行基本的數學計算，包括加法、減法、乘法和除法。",
    func=math_calculator
)

# 創建日期轉換工具
date_tool = Tool(
    name="date_converter",
    description="將日期從 YYYY-MM-DD 格式轉換為指定格式。",
    func=date_converter
)

# 設置工具和LLM
tools = [math_tool, date_tool]
llm = ChatOpenAI(model="gpt-4o-mini")
llm_with_tools = llm.bind_tools(tools + [RequestAssistance])

# 定義聊天機器人節點
def chatbot(state: State):
    response = llm_with_tools.invoke(state["messages"])
    ask_human = False
    if (
        response.tool_calls
        and response.tool_calls[0]["name"] == RequestAssistance.__name__
    ):
        ask_human = True
    return {"messages": [response], "ask_human": ask_human}

# 定義人工節點
def create_response(response: str, ai_message: AIMessage):
    return ToolMessage(
        content=response,
        tool_call_id=ai_message.tool_calls[0]["id"],
    )

def human_node(state: State):
    new_messages = []
    if not isinstance(state["messages"][-1], ToolMessage):
        new_messages.append(
            create_response("沒有收到人工回應。", state["messages"][-1])
        )
    return {
        "messages": new_messages,
        "ask_human": False,
    }

# 定義節點選擇邏輯
def select_next_node(state: State):
    if state["ask_human"]:
        return "human"
    if state["messages"][-1].tool_calls:
        return "tools"
    return END

# 構建圖
graph_builder = StateGraph(State)
graph_builder.add_node("chatbot", chatbot)
graph_builder.add_node("tools", ToolNode(tools=tools))
graph_builder.add_node("human", human_node)

graph_builder.add_edge(START, "chatbot")
graph_builder.add_conditional_edges(
    "chatbot",
    select_next_node,
    {"human": "human", "tools": "tools", END: END},
)
graph_builder.add_edge("human", "chatbot")
graph_builder.add_edge("tools", "chatbot")

# 編譯圖
memory = MemorySaver()
graph = graph_builder.compile(
    checkpointer=memory,
    interrupt_before=["human"],
)

# from IPython.display import Image, display
# display(Image(graph.get_graph().draw_mermaid_png()))

# 使用範例
config = {"configurable": {"thread_id": "1"}}

# 初始對話
events = graph.stream(
    {"messages": [("user", "你好，我正在學習 LangGraph。你能告訴我它的主要特點嗎？")]},
    config,
    stream_mode="values"
)
for event in events:
    if "messages" in event:
        event["messages"][-1].pretty_print()

# 繼續對話，使用數學計算工具
events = graph.stream(
    {"messages": [("user", "太好了！現在，你能幫我計算 15.5 * 3 - 7.2 嗎？")]},
    config,
    stream_mode="values"
)
for event in events:
    if "messages" in event:
        event["messages"][-1].pretty_print()

# 使用日期轉換工具
events = graph.stream(
    {"messages": [("user", "謝謝。接下來，你能將日期 2023-11-08 轉換為中文格式嗎？")]},
    config,
    stream_mode="values"
)
for event in events:
    if "messages" in event:
        event["messages"][-1].pretty_print()

# 超出能力範圍
events = graph.stream(
    {"messages": [("user", "我需要你幫我審核並簽署一份重要的法律文件，這份文件涉及公司的重大決策。")]},
    config,
    stream_mode="values"
)
for event in events:
    if "messages" in event:
        event["messages"][-1].pretty_print()

# 展示時間旅行功能
# print("\n時間旅行功能演示：")
# for state in graph.get_state_history(config):
#     print(f"訊息數量：{len(state.values['messages'])}, 下一步：{state.next}")
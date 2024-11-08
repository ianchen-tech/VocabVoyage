from typing import TypedDict, Annotated, Sequence
import operator
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, END, START
from langchain.schema import HumanMessage, AIMessage
from langchain_core.messages import BaseMessage
import graphviz

class AllState(TypedDict):
    messages: Annotated[Sequence[str], operator.add]

def get_taiwan_weather(city: str) -> str:
    """查詢台灣特定城市的天氣狀況。"""
    weather_data = {
        "台北": "晴天，溫度28°C",
        "台中": "多雲，溫度26°C",
        "高雄": "陰天，溫度30°C",
        "新竹": "晴時多雲，溫度25°C",
        "台南": "多雲時晴，溫度29°C"
    }
    return f"{city}的天氣：{weather_data.get(city, '暫無資料')}"

def create_weather_chain():
    model = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.7,
        max_tokens=None,
        timeout=None,
        max_retries=2,
    )

    # 城市提取提示
    extract_city_prompt = """
    您需要從問題中提取城市名稱
    只需回覆城市名稱，如果找不到城市名稱請回覆 '您無指定城市'
    
    問題內容：
    {user_query}
    """
    extract_prompt = ChatPromptTemplate.from_template(extract_city_prompt)

    # 回應生成提示
    response_prompt = """
    請根據提供的天氣資訊，回答用戶的問題
    
    用戶問題：
    {user_query}
    
    天氣資訊：
    {information}
    """
    response_template = ChatPromptTemplate.from_template(response_prompt)

    # 創建鏈
    extract_chain = extract_prompt | model
    response_chain = response_template | model

    def call_model(state: AllState):
        messages = state["messages"]
        response = extract_chain.invoke({"user_query": messages[0]})
        return {"messages": [response]}

    def weather_tool(state: AllState):
        context = state["messages"]
        city_name = context[1].content
        weather_info = get_taiwan_weather(city_name)
        return {"messages": [weather_info]}

    def query_classify(state: AllState):
        messages = state["messages"]
        if messages[1].content == "您無指定城市":
            return "end"
        return "continue"

    def responder(state: AllState):
        messages = state["messages"]
        response = response_chain.invoke({
            "user_query": messages[0],
            "information": messages[2]
        })
        return {"messages": [response]}

    # 建立圖形
    workflow = StateGraph(AllState)
    
    # 添加節點
    workflow.add_node("extract_city", call_model)
    workflow.add_node("get_weather", weather_tool)
    workflow.add_node("generate_response", responder)
    
    # 添加條件邊
    workflow.add_conditional_edges(
        "extract_city",
        query_classify,
        {
            "continue": "get_weather",
            "end": END
        }
    )
    
    # 添加一般邊
    workflow.add_edge("get_weather", "generate_response")
    
    # 設置入口和出口
    workflow.set_entry_point("extract_city")
    workflow.set_finish_point("generate_response")

    return workflow.compile()

def process_weather_query(query: str):
    """處理天氣查詢請求"""
    app = create_weather_chain()
    init_state = {"messages": [query]}
    response = app.invoke(init_state)
    return response['messages'][-1].content

def generate_workflow_graph():
    workflow = create_weather_chain()
    dot = graphviz.Digraph()
    dot.attr(rankdir='TB')
    # 添加節點
    dot.node('START', 'Start')
    dot.node('extract_city', 'Extract City')
    dot.node('get_weather', 'Get Weather')
    dot.node('generate_response', 'Generate Response')
    dot.node('END', 'End')

    # 添加邊
    dot.edge('START', 'extract_city')
    dot.edge('extract_city', 'get_weather', label='City found')
    dot.edge('extract_city', 'END', label='No city')
    dot.edge('get_weather', 'generate_response')
    dot.edge('generate_response', 'END')

    return dot

if __name__ == "__main__":
    # 測試用例
    test_queries = [
        "請問台北今天天氣如何？",
        "倫敦現在的天氣狀況是什麼？",
        "高雄今天會下雨嗎？",
        "我想知道未來三天會不會下雨",
    ]
    
    for query in test_queries:
        print(f"\n問題：{query}")
        print(f"回答：{process_weather_query(query)}")

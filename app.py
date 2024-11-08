import streamlit as st
from graph import process_weather_query, generate_workflow_graph
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(page_title="Weather Chatbot")

# 側邊欄導航
with st.sidebar:
    st.title("🚀 功能導航")
    app_mode = st.selectbox("[ Mode ]", ["Chatbot", "Workflow"])

# 主要內容區域
if app_mode == "Chatbot":
    st.title("Weather Chatbot")

    # 初始化聊天歷史
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # 顯示聊天歷史
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # 用戶輸入
    if prompt := st.chat_input("詢問指定城市天氣（例如：台北今天天氣如何？）"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # 使用 process_weather_query 函數處理對話
        response = process_weather_query(prompt)

        # 顯示助手回應
        with st.chat_message("assistant"):
            st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

elif app_mode == "Workflow":
    st.title("Workflow")
    
    # 顯示流程圖
    dot = generate_workflow_graph()
    st.graphviz_chart(dot)
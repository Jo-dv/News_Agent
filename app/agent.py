import os
import operator
import re
from datetime import datetime, timedelta
from typing import Annotated, List, TypedDict

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage, AnyMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import ToolNode

import chromadb
import chromadb.utils.embedding_functions as embedding_functions

from prompts import get_agent_system_prompt, get_report_generation_prompt, get_chat_prompt

# --- [1. 상태(State) 정의] ---
class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    final_report: str
    is_initial_run: bool
    user_query: str
    chat_response: str

# --- [2. 도구 설정] ---
search_tool = TavilySearchResults(
    max_results=2, 
    include_raw_content=False,
    topic="news",
    days=7
)
tools = [search_tool]
tool_node = ToolNode(tools) # 도구 실행 노드

# --- [3. LLM 및 DB 설정] ---
# 도구를 사용하는 에이전트용 LLM
llm = ChatOpenAI(model="gpt-5.4-mini", temperature=0)
llm_with_tools = llm.bind_tools(tools)

# 문서 저장용 일반 LLM
report_llm = ChatOpenAI(model="gpt-5.4-mini", temperature=0.2)

embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.environ.get("OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)

chroma_client = chromadb.PersistentClient(path="./chroma_data")
collection = chroma_client.get_or_create_collection(
    name="financial_reports",
    embedding_function=openai_ef
)

memory = MemorySaver()

# --- [4. 노드 함수 정의] ---

def agent_node(state: AgentState):
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    last_week = (now - timedelta(days=7)).strftime("%Y-%m-%d")

    # 프롬프트 파일에서 가져오기
    system_prompt = get_agent_system_prompt(last_week, today)
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

def generate_report_node(state: AgentState):
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    last_week = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    
    # 프롬프트 파일에서 가져오기
    prompt = get_report_generation_prompt(last_week, today)
    
    messages_to_pass = state["messages"]
    if hasattr(messages_to_pass[-1], 'tool_calls') and messages_to_pass[-1].tool_calls:
        messages_to_pass = messages_to_pass[:-1]
    
    report_request = messages_to_pass + [HumanMessage(content=prompt)]
    response = report_llm.invoke(report_request)
    return {"final_report": response.content}

def rag_store_node(state: AgentState):
    """최종 리포트를 클리닝하여 벡터 DB에 저장"""
    today_str = datetime.now().strftime("%Y-%m-%d")
    final_report = state.get("final_report", "")
    
    # 앞서 논의한 노이즈(마크다운, 줄바꿈 등) 제거 로직 적용
    def clean_text(text):
        if not text: return ""
        text = re.sub(r'[\*\#\-\[\]]', '', text)
        text = text.replace('\\n', ' ').replace('\n', ' ').replace('\\', '')
        text = re.sub(r'\s+', ' ', text).strip()
        return text

    cleaned_content = clean_text(final_report)
    
    meta_info = {
        "title": f"{today_str}_react_report",
        "date": today_str,
        "type": "weekly_structured_report"
    }
    
    # DB 적재 (os, chromadb, json 등이 여기서 활용됨)
    collection.upsert(
        documents=[cleaned_content],
        metadatas=[meta_info],
        ids=[f"report_{today_str}"]
    )
    
    return state

def chat_and_rag_node(state: AgentState):
    query = state.get("user_query")
    results = collection.query(query_texts=[query], n_results=3)
    
    context = ""
    if results and results.get('documents') and results['documents'][0]:
        context = "\n\n".join(results['documents'][0])
        
    # 프롬프트 파일에서 가져오기
    prompt = get_chat_prompt(context, query)
    
    response = report_llm.invoke([HumanMessage(content=prompt)])
    
    if "내용이 없습니다" in response.content or "없습니다" in response.content:
        return {"chat_response": "제공된 리포트 DB에 관련된 내용이 없습니다."}
        
    return {"chat_response": response.content}

# --- [5. 워크플로우 그래프 및 라우팅] ---

def should_continue(state: AgentState):
    """에이전트의 마지막 메시지와 전체 루프 길이를 확인하여 라우팅 결정"""
    messages = state.get("messages", [])
    last_message = messages[-1]
    
    # [Fallback 로직] 메시지가 8개 이상 쌓였다면 (약 3~4회 루프 반복)
    # 에이전트가 헤매고 있다고 판단하고 억지로 리포트 작성으로 넘김
    if len(messages) >= 8:
        print("\n[Fallback 발동] 에이전트 검색 루프 한계 도달. 지금까지 수집한 데이터로 리포트를 강제 작성합니다.")
        return "generate_report"
        
    # 정상 로직: 도구 호출이 있으면 action 노드로, 없으면 리포트 작성으로
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "action"
        
    return "generate_report"

def route_request(state: AgentState):
    if state.get("is_initial_run", False):
        return "agent" # ReAct 루프 시작
    return "chat_and_rag"

workflow = StateGraph(AgentState)

# 노드 등록
workflow.add_node("agent", agent_node)
workflow.add_node("action", tool_node)
workflow.add_node("generate_report", generate_report_node)
workflow.add_node("rag_store", rag_store_node)
workflow.add_node("chat_and_rag", chat_and_rag_node)

# 진입점 설정
workflow.set_conditional_entry_point(
    route_request,
    {"agent": "agent", "chat_and_rag": "chat_and_rag"}
)

# ReAct 루프 엣지 설정
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "action": "action",
        "generate_report": "generate_report"
    }
)

# action 노드가 끝나면 다시 agent 노드로 돌아가서 결과를 확인하도록 강제
workflow.add_edge("action", "agent")

# 리포트 작성 -> DB 적재 -> 종료
workflow.add_edge("generate_report", "rag_store")
workflow.add_edge("rag_store", END)
workflow.add_edge("chat_and_rag", END)

financial_agent_app = workflow.compile(checkpointer=memory)
config = {"configurable": {"thread_id": "react_financial_thread"}}
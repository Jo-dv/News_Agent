import os
import operator
import json
from datetime import datetime
from typing import Annotated, List, TypedDict

from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.tools.tavily_search.tool import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, AnyMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

import chromadb
import chromadb.utils.embedding_functions as embedding_functions

class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    banking_data: str 
    source_urls: Annotated[List[str], operator.add]
    reasoning_log: Annotated[List[str], operator.add]
    final_report: str
    is_initial_run: bool
    user_query: str
    chat_response: str

llm = ChatOpenAI(model="gpt-5.4-mini", temperature=0.2)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
search_tool = TavilySearchResults(max_results=8, include_raw_content=True, topic="news")
memory = MemorySaver()

# --- [3. DB 연결 (ChromaDB)] ---
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.environ.get("OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)

chroma_client = chromadb.PersistentClient(path="./chroma_data")
collection = chroma_client.get_or_create_collection(
    name="financial_reports",
    embedding_function=openai_ef
)

# --- [4. 노드 함수 정의] ---
def banking_search_node(state: AgentState):
    """오늘 기준 은행 산업 단일 검색 노드"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 쿼리에 오늘 날짜를 강제하여 최신 기사만 검색 유도
    query = f"date:{today} 대한민국 시중 은행 주요 뉴스"
    search_results = search_tool.invoke({"query": query})
    
    urls = [res.get('url') for res in search_results if res.get('url')]
    trimmed_results = [{"title": r.get('title'), "content": r.get('content', '')[:1000]} for r in search_results]

    safe_data_str = json.dumps(trimmed_results, ensure_ascii=False)

    # 프롬프트: 오늘 발행된 팩트만 취합하도록 강제
    prompt = f"""기준일: {today}
    제공된 데이터는 오늘({today}) 검색된 대한민국 은행 산업 관련 문서들입니다.
    반드시 오늘 날짜와 관련된 핵심 이슈 3가지만 분석하십시오. 과거 데이터는 무시하십시오.
    억지 칭찬이나 불필요한 미사여구는 배제하고, 객관적인 수치와 팩트 위주로 작성하십시오.
    
    데이터: {safe_data_str}
    
    요약 전, 당신의 판단 논리를 '[추론: 은행 분석]' 이라는 텍스트로 시작하여 1줄로 명시하십시오."""
    
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content
    
    reasoning = ""
    if "[추론: 은행 분석]" in content:
        reasoning = content.split("\n")[0]

    return {
        "banking_data": content, 
        "source_urls": urls,
        "reasoning_log": [reasoning] if reasoning else []
    }

def generate_report_node(state: AgentState):
    """검색된 은행 데이터를 바탕으로 리포트 생성"""
    today = datetime.now().strftime("%Y-%m-%d")
    reasoning_logs = "\n".join([f"- {log}" for log in state.get("reasoning_log", []) if log])
    
    prompt = f"""
    아래 데이터를 바탕으로 {today} 기준 [국내 은행 산업 일일 리포트]를 작성하십시오.
    제공된 데이터 외의 외부 지식이나 과거 데이터는 섞지 마십시오. 감정적 표현 없이 건조하고 명확하게 작성하십시오.

    은행 산업 이슈: {state.get('banking_data', '')}

    ---
    ### 템플릿 가이드 ###

    ■ 1. 에이전트 추론 과정
    {reasoning_logs}

    -----------------------------------------
    ■ 2. 오늘의 핵심 요약
    - (당일 은행 산업을 관통하는 가장 중요한 흐름 1~2줄 요약)

    -----------------------------------------
    ■ 3. 주요 뉴스 상세 (팩트 위주)
    - 
    - 
    - 

    -----------------------------------------
    ■ 4. 주요 출처
    {state.get('source_urls', [])}
    ---
    """
    
    response = llm.invoke([
        SystemMessage(content="지시된 템플릿 형식에 맞춰 묻는 말에만 현실적이고 논리적으로 대답하십시오. 추임새는 철저히 배제하십시오."),
        HumanMessage(content=prompt)
    ])
    
    return {"final_report": response.content, "messages": [AIMessage(content=response.content)]}

def rag_store_node(state: AgentState):
    """생성된 데이터를 벡터 DB에 저장"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    db_payload = {
        "title": f"{today} 국내 은행 산업 동향",
        "date": today,
        "content": state.get('banking_data', ''),
        "link": state.get("source_urls", [])
    }
    
    json_document = json.dumps(db_payload, ensure_ascii=False)
    
    meta_info = {
        "title": f"{today}_banking_report",
        "date": today,
        "type": "daily_banking_report"
    }
    
    collection.upsert(
        documents=[json_document],
        metadatas=[meta_info],
        ids=[f"report_{today}"]
    )
    
    return state

def chat_and_rag_node(state: AgentState):
    """DB 기반 질의응답 노드"""
    query = state.get("user_query")
    
    results = collection.query(query_texts=[query], n_results=3)
    
    context = ""
    if results and results.get('documents') and results['documents'][0]:
        context = "\n\n".join(results['documents'][0])
        
    prompt = f"""
    당신은 오직 제공된 [참고 자료]에 기반해서만 답변하는 엄격한 데이터 에이전트입니다.

    [참고 자료]
    {context}

    [사용자 질문]
    {query}

    [절대 규칙]
    1. [참고 자료]에 사용자의 질문에 대한 직접적인 내용이 없다면, 반드시 "제공된 리포트 DB에 관련된 내용이 없습니다."라고만 출력하고 즉시 종료하십시오.
    2. 사전 지식이나 일반 상식은 절대 사용하지 마십시오.
    3. 추임새나 친절한 설명은 빼고, 묻는 것에만 논리에 맞춰 현실적으로 대답하십시오.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    return {"chat_response": response.content}

# --- [5. 워크플로우 그래프 빌드] ---
def route_request(state: AgentState):
    if state.get("is_initial_run", False):
        return "banking_search" # 수정됨
    return "chat_and_rag"

workflow = StateGraph(AgentState)
workflow.add_node("banking_search", banking_search_node)
workflow.add_node("generate_report", generate_report_node)
workflow.add_node("rag_store", rag_store_node)
workflow.add_node("chat_and_rag", chat_and_rag_node)

workflow.set_conditional_entry_point(
    route_request,
    {"banking_search": "banking_search", "chat_and_rag": "chat_and_rag"}
)

workflow.add_edge("banking_search", "generate_report")
workflow.add_edge("generate_report", "rag_store")
workflow.add_edge("rag_store", END)
workflow.add_edge("chat_and_rag", END)

financial_agent_app = workflow.compile(checkpointer=memory)

# --- [6. 설정] ---
config = {"configurable": {"thread_id": "daily_report_thread"}}
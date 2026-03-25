import os
import operator
import uuid
from datetime import datetime
from typing import Annotated, List, TypedDict
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.tools.tavily_search.tool import TavilySearchResults
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, AnyMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
import operator
import chromadb
import chromadb.utils.embedding_functions as embedding_functions
import json

class AgentState(TypedDict):
    messages: Annotated[List[AnyMessage], operator.add]
    macro_context: str
    domain_data: dict
    source_urls: Annotated[List[str], operator.add]
    reasoning_log: Annotated[List[str], operator.add]  # 추가: 추론 과정 누적
    final_report: str
    is_initial_run: bool
    user_query: str
    chat_response: str

llm = ChatOpenAI(model="gpt-5.4-mini", temperature=0.2)
embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
search_tool = TavilySearchResults(max_results=3, include_raw_content=True) 
memory = MemorySaver() # 세션 기억을 위한 체크포인터
today_date = datetime.now().strftime("%Y-%m-%d")
openai_ef = embedding_functions.OpenAIEmbeddingFunction(
    api_key=os.environ.get("OPENAI_API_KEY"),
    model_name="text-embedding-3-small"
)

chroma_client = chromadb.PersistentClient(path="./chroma_data")
collection = chroma_client.get_or_create_collection(
    name="financial_reports",
    embedding_function=openai_ef
)

def macro_search_node(state: AgentState):
    today = datetime.now().strftime("%Y-%m-%d")
    
    # 1. 당일 검색 강제
    query = f"{today} 대한민국 경제 지표 코스피 환율 뉴스"
    search_results = search_tool.invoke({"query": query})
    
    urls = [res.get('url') for res in search_results if res.get('url')]
    trimmed_results = [{"title": r.get('title'), "content": r.get('content', '')[:1000]} for r in search_results]

    safe_data_str = json.dumps(trimmed_results, ensure_ascii=False)

    # 2. 프롬프트에 추론 과정 요구
    prompt = f"""
    기준일: {today}
    제공된 데이터에서 반드시 기준일 당일에 발생한 뉴스만 선별하십시오. 과거 데이터는 무시하십시오.
    
    데이터: {safe_data_str}
    
    요약 전, 이 데이터들을 바탕으로 국내 거시 경제가 어떤 흐름을 보이고 있는지 당신의 판단 논리를 '[추론: 거시 분석]' 이라는 텍스트로 시작하여 2줄로 명시하십시오. 그 후 요약하십시오.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    content = response.content
    
    # 응답에서 추론 부분만 추출하여 로그에 저장 (단순 분리)
    reasoning = ""
    if "[추론: 거시 분석]" in content:
        reasoning = content.split("\n")[0] # 첫 줄에 추론이 있다고 가정

    return {
        "macro_context": content,
        "source_urls": urls,
        "reasoning_log": [reasoning] if reasoning else []
    }

def micro_search_node(state: AgentState):
    today = datetime.now().strftime("%Y-%m-%d")
    macro_context = state.get("macro_context", "")
    domains = ["은행", "카드", "보험", "증권"]
    domain_results = {}
    all_urls = []
    all_reasoning = []

    for domain in domains:
        query = f"{today} 한국 {domain} 산업 뉴스"
        search_results = search_tool.invoke({"query": query})
        
        urls = [res.get('url') for res in search_results if res.get('url')]
        all_urls.extend(urls)
        
        trimmed_results = [{"title": r.get('title'), "content": r.get('content', '')[:1000]} for r in search_results]
        
        safe_data_str = json.dumps(trimmed_results, ensure_ascii=False)

        prompt = f"""
        기준일: {today}
        거시 경제 흐름: {macro_context[:300]}
        
        제공된 데이터에서 기준일 당일 뉴스만 선별하십시오.
        데이터: {safe_data_str}
        
        거시 경제 흐름이 {domain} 산업에 미치는 영향을 바탕으로 어떤 이슈를 우선적으로 필터링했는지 판단 논리를 '[추론: {domain} 분석]'으로 시작하여 1줄로 작성 후 이슈를 요약하십시오.
        """
        
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        domain_results[domain] = content
        
        if f"[추론: {domain} 분석]" in content:
            all_reasoning.append(content.split("\n")[0])

    return {
        "domain_data": domain_results,
        "source_urls": all_urls,
        "reasoning_log": all_reasoning
    }

def merge_node(state: AgentState):
    today = datetime.now().strftime("%Y-%m-%d")
    reasoning_logs = "\n".join([f"- {log}" for log in state.get("reasoning_log", []) if log])
    
    prompt = f"""
    아래 데이터를 바탕으로 {today} 기준 [금융 인사이트 리포트]를 작성하십시오.
    제공된 데이터 외의 외부 지식이나 과거 데이터는 섞지 마십시오.

    거시 동향: {state.get('macro_context', '')}
    산업 이슈: {state.get('domain_data', {})}

    ---
    ### 템플릿 가이드 ###

    ■ 1. 에이전트 추론 과정 (Agent's Reasoning)
    {reasoning_logs}

    -----------------------------------------
    ■ 2. 오늘의 핵심 요약
    - (당일 거시 경제와 4대 산업을 관통하는 가장 중요한 흐름 요약)

    -----------------------------------------
    ■ 3. 주요 뉴스 상세 (거시 및 산업별 핵심 팩트)
    (이전과 동일하게 주요 이슈 나열)

    -----------------------------------------
    ■ 4. 출처 (Sources)
    {state.get('source_urls', [])}
    ---
    """
    
    response = llm.invoke([
        SystemMessage(content="지시된 템플릿 형식에 맞춰 팩트만 전달하십시오."),
        HumanMessage(content=prompt)
    ])
    
    return {"final_report": response.content, "messages": [AIMessage(content=response.content)]}

def rag_store_node(state: AgentState):
    raw_data = state.get("raw_search_data", {})
    final_report = state.get("final_report", "")
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    docs, metadatas, ids = [], [], []
    for category, content in raw_data.items():
        docs.append(content)
        metadatas.append({"date": today_str, "type": "raw_search", "category": category})
        ids.append(f"{today_str}-raw-{category}-{uuid.uuid4().hex[:8]}")
        
    docs.append(final_report)
    metadatas.append({"date": today_str, "type": "final_report", "category": "all"})
    ids.append(f"{today_str}-report-{uuid.uuid4().hex[:8]}")
    
    embeds = embeddings.embed_documents(docs)
    collection.add(documents=docs, embeddings=embeds, metadatas=metadatas, ids=ids)
    return state

def chat_and_rag_node(state: AgentState):
    query = state.get("user_query")
    
    # DB 검색 로직 (예시)
    results = collection.query(query_texts=[query], n_results=3)
    
    context = ""
    if results and results.get('documents') and results['documents'][0]:
        context = "\n\n".join(results['documents'][0])
        
    # [핵심] LLM의 외부 지식 개입을 완벽히 차단하는 프롬프트
    prompt = f"""
    당신은 오직 제공된 [참고 자료]에 기반해서만 답변하는 엄격한 금융 데이터 에이전트입니다.

    [참고 자료]
    {context}

    [사용자 질문]
    {query}

    [절대 규칙]
    1. [참고 자료]에 사용자의 질문에 대한 직접적인 내용이 없다면, 반드시 "제공된 금융 리포트 DB에 관련된 내용이 없습니다."라고만 출력하고 답변을 즉시 종료하십시오.
    2. 당신이 학습한 사전 지식이나 일반 상식(예: 비행기, 날씨, 일상 대화 등)을 절대 섞어 쓰지 마십시오.
    3. 친절하게 설명하려 하지 말고, 오직 [참고 자료]의 팩트만 전달하십시오.
    """
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    return {"chat_response": response.content}

def route_request(state: AgentState):
    """실행 의도에 따라 노드 라우팅"""
    if state.get("is_initial_run", False):
        return "macro_search"
    return "chat_and_rag"

workflow = StateGraph(AgentState)
workflow.add_node("macro_search", macro_search_node)
workflow.add_node("micro_search", micro_search_node)
workflow.add_node("merge_report", merge_node)
workflow.add_node("rag_store", rag_store_node)
workflow.add_node("chat_and_rag", chat_and_rag_node)

# 라우터 진입점 설정
workflow.set_conditional_entry_point(
    route_request,
    {"macro_search": "macro_search", "chat_and_rag": "chat_and_rag"}
)

workflow.add_edge("macro_search", "micro_search")
workflow.add_edge("micro_search", "merge_report")
workflow.add_edge("merge_report", "rag_store")
workflow.add_edge("rag_store", END)
workflow.add_edge("chat_and_rag", END)

# 메모리 체크포인터를 장착하여 컴파일
financial_agent_app = workflow.compile(checkpointer=memory)
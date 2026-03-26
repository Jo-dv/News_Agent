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

    system_prompt = f"""당신은 자율적으로 판단하는 금융 데이터 에이전트입니다.
    분석 범위: {last_week} ~ {today}
    
    [미션] 
    1. 거시 경제와 4대 금융 산업(은행, 카드, 보험, 증권)의 핵심 뉴스를 파악하십시오.
    
    [ReAct 탈출 및 사고 규칙 - 절대 준수]
    1. 정보가 부족하면 검색 도구를 사용하십시오. (다중 검색 권장)
    2. **도구를 호출하기 전에는 반드시 "어떤 데이터가 부족해서 무슨 키워드로 추가 검색을 하는지" 판단 이유를 텍스트로 먼저 명시하십시오. 이유 설명 없이 도구만 호출하는 것을 금지합니다.**
    3. 충분한 정보가 모였다고 판단되면 즉시 도구 사용을 중단하십시오.
    4. 도구 사용을 멈출 때는 "원하시면 다음 단계로..." 같은 불필요한 대화나 사용자에게 묻는 질문을 절대 하지 마십시오.
    5. 분석이 끝나면 오직 "정보 수집 완료"라는 단 6글자만 출력하고 행동을 종료하십시오.
    """
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm_with_tools.invoke(messages)
    
    return {"messages": [response]}

def generate_report_node(state: AgentState):
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    last_week = (now - timedelta(days=7)).strftime("%Y-%m-%d")
    
    prompt = f"""
    아래는 당신이 도구를 사용해 수집하고 분석한 전체 기록입니다.
    이 기록들을 바탕으로 {last_week} ~ {today} 기준 [주간 금융 인사이트 리포트]를 작성하십시오.
    
    ---
    ### 템플릿 가이드 ###
    ■ 1. 에이전트 추론 요약
    ■ 2. 주간 핵심 요약
    ■ 3. 주요 뉴스 상세 (거시, 은행, 카드, 보험, 증권 팩트 위주)
    ■ 4. 주요 출처 (참고한 URL들)
    ---

    [절대 규칙]
    1. 지정된 1~4번 템플릿 항목 내용 외에는 단 한 글자도 출력하지 마십시오.
    2. "원하시면 다음 단계로", "도움이 필요하시면" 등 사용자의 의향을 묻는 인사말이나 안내문구를 절대 추가하지 마십시오.
    3. 4번 주요 출처 작성이 끝나면 문장을 닫고 즉시 텍스트 생성을 종료하십시오.
    4. 제공된 검색 데이터 중에서 날짜가 {last_week} 이전인 과거 데이터(예: 1~2달 전 기사)는 무조건 폐기하십시오. 만약 특정 산업에 최신 데이터가 아예 없다면 억지로 과거 기사를 쓰지 말고 "이번 주 주요 이슈 없음"이라고만 기재하십시오.
    """
    
    # 1. 기존 메시지 기록 가져오기
    messages_to_pass = state["messages"]
    
    # 2. [에러 방지 핵심] 마지막 메시지가 도구 호출을 포함하고 있다면, 그 메시지는 버림
    if hasattr(messages_to_pass[-1], 'tool_calls') and messages_to_pass[-1].tool_calls:
        messages_to_pass = messages_to_pass[:-1]
    
    # 3. 정제된 메시지에 리포트 작성 프롬프트를 붙여서 실행
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
    """사용자 질의응답 (엄격한 프롬프트 적용)"""
    query = state.get("user_query")
    results = collection.query(query_texts=[query], n_results=3)
    
    context = ""
    if results and results.get('documents') and results['documents'][0]:
        context = "\n\n".join(results['documents'][0])
        
    prompt = f"""
    당신은 제공된 [참고 자료]만 읽고 답변하는 엄격한 금융 데이터 분석가입니다.

    [참고 자료]
    {context}

    [사용자 질문]
    {query}

    [응답 지침 - 최우선 순위]
    1. [참고 자료]에 사용자의 질문과 관련된 단어나 맥락이 조금이라도 포함되어 있다면, 그것을 바탕으로 최대한 답변을 구성하십시오.(관련 내용이 아예 단 하나도 없을 때만 "제공된 리포트 DB에 관련된 내용이 없습니다."라고 출력하십시오.)
    2. 자료에 내용이 있다면, 질문에 대해서만 논리적이고 건조하게 답변하십시오.
    3. 당신의 개인적인 상식이나 추임새는 철저히 배제하십시오.
    """
    
    response = report_llm.invoke([HumanMessage(content=prompt)])
    
    # 혹시라도 LLM이 말을 안 들을 때를 대비한 강제 차단 방어벽
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
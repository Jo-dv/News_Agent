import os
import asyncio
import discord
from dotenv import load_dotenv
from agent import financial_agent_app
from email_sender import send_report_email 

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# 동일한 thread_id를 사용해야 에이전트가 이전 대화와 리포트 문맥을 기억합니다.
THREAD_ID = "discord_financial_session_1"
config = {"configurable": {"thread_id": THREAD_ID}}

async def run_initial_briefing():
    channel_id = os.getenv("DISCORD_CHANNEL_ID")
    if not channel_id:
        print("경고: DISCORD_CHANNEL_ID가 없어 디스코드로 리포트를 전송할 수 없습니다.")
        return

    channel = client.get_channel(int(channel_id))
    await channel.send("에이전트가 데이터 검색 및 리포트 작성을 시작합니다...")
    
    initial_state = {
        "messages": [],
        "is_initial_run": True, # 하향식 리포트 생성 파이프라인 트리거
        "user_query": ""
    }
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, lambda: financial_agent_app.invoke(initial_state, config=config))
    
    final_report = result.get("final_report", "에러: 리포트 생성 실패")
    
    # 1. 디스코드 채널에 리포트 전송 (길이 제한 2000자 대비 분할 전송)
    for chunk in [final_report[i:i+1900] for i in range(0, len(final_report), 1900)]:
        await channel.send(chunk)
    await channel.send("리포트 작성 및 RAG 적재가 완료되었습니다. 추가 질문이나 수정 지시를 챗으로 남겨주세요.")
    
    # 2. 이메일 발송
    try:
        await loop.run_in_executor(None, send_report_email, final_report)
    except Exception as e:
        print(f"이메일 발송 실패: {e}")

@client.event
async def on_ready():
    print(f'디스코드 봇 연결 완료: {client.user}')
    await run_initial_briefing()

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # 사용자가 채팅을 치면 RAG 상호작용 파이프라인 트리거
    if message.content:
        # 봇이 입력 중임을 표시
        async with message.channel.typing():
            state = {
                "is_initial_run": False, # 질의응답(RAG) 모드 트리거
                "user_query": message.content
            }
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: financial_agent_app.invoke(state, config=config))
            
            answer = result.get("chat_response", "응답을 생성하지 못했습니다.")
            
            for chunk in [answer[i:i+1900] for i in range(0, len(answer), 1900)]:
                await message.channel.send(chunk)

if __name__ == "__main__":
    token = os.getenv("DISCORD_BOT_TOKEN")
    client.run(token)
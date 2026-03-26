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

@client.event
async def on_ready():
    print(f'디스코드 봇 연결 완료: {client.user}')
    print("명령어 대기 중: !리포트생성, !종료")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # 1. 봇 및 컨테이너 종료 명령어
    if message.content == "!종료":
        await message.channel.send("🛑 컨테이너를 종료합니다.")
        await client.close()
        return

    # 2. 리포트 생성 프로세스 트리거 (실시간 로그 출력 + 메일 전송만)
    if message.content == "!리포트생성":
        await message.channel.send("🚀 리포트 생성 프로세스를 시작합니다...")
        
        try:
            state = {
                "messages": [],
                "is_initial_run": True, 
                "user_query": ""
            }
            
            final_report = ""
            
            # astream()을 사용하여 각 노드의 작업이 끝날 때마다 로그를 출력합니다.
            async for output in financial_agent_app.astream(state, config=config):
                for node_name, node_state in output.items():
                    if node_name == "macro_search":
                        await message.channel.send("📊 [1/4] 거시 경제 동향 검색 및 분석 완료")
                    elif node_name == "micro_search":
                        await message.channel.send("🏦 [2/4] 4대 금융 산업 뉴스 검색 및 분석 완료")
                    elif node_name == "merge_report":
                        await message.channel.send("📝 [3/4] 전체 인사이트 리포트 취합 완료")
                        # 병합 단계에서 생성된 리포트를 변수에 따로 저장합니다 (디스코드에는 출력하지 않음)
                        final_report = node_state.get("final_report", "")
                    elif node_name == "rag_store":
                        await message.channel.send("💾 [4/4] 벡터 DB 데이터 적재 완료")
            
            if not final_report:
                raise ValueError("리포트 텍스트가 비어 있습니다. 검색된 데이터가 없을 수 있습니다.")

            # 리포트 디스코드 출력 과정 생략 -> 바로 이메일 발송
            await message.channel.send("📧 결과 리포트를 이메일로 발송하는 중입니다...")
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, send_report_email, final_report)
            
            await message.channel.send("✅ 모든 작업이 완료되었습니다! 이메일 보관함을 확인해 주세요.\n(DB에 적재된 오늘자 리포트 내용에 대해 질문하시거나, 끝내려면 `!종료`를 입력하십시오.)")
                
        # 리포트 생성 중 에러 발생 시 로그를 남기고 컨테이너 강제 종료
        except Exception as e:
            await message.channel.send(f"❌ [Error Log] 에러 발생: {str(e)}\n🛑 에러가 발생하여 컨테이너를 강제 종료합니다.")
            print(f"에러 발생으로 인한 컨테이너 강제 종료: {e}")
            await client.close()
            
        return

    # 3. 일반 채팅 (RAG 질의응답 모드 트리거)
    if message.content:
        async with message.channel.typing():
            try:
                state = {
                    "is_initial_run": False,
                    "user_query": message.content
                }
                
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: financial_agent_app.invoke(state, config=config))
                
                answer = result.get("chat_response", "응답을 생성하지 못했습니다.")
                
                for chunk in [answer[i:i+1900] for i in range(0, len(answer), 1900)]:
                    await message.channel.send(chunk)
                    
            except Exception as e:
                await message.channel.send(f"❌ 질의응답 중 에러 발생: {str(e)}\n🛑 컨테이너를 강제 종료합니다.")
                print(f"질의응답 중 에러: {e}")
                await client.close()

if __name__ == "__main__":
    token = os.environ.get("DISCORD_BOT_TOKEN")
    
    if not token:
        print("❌ 에러: DISCORD_TOKEN을 찾을 수 없습니다. .env 파일을 확인하세요.")
    else:
        client.run(token)
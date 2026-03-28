import uuid
import discord
import asyncio
import os
from agent import financial_agent_app, config
from email_sender import send_report_email # 이메일 발송 모듈
from dotenv import load_dotenv
import traceback
import datetime

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f"✅ 디스코드 봇 연결 완료: {client.user}. '!리포트생성' 명령어를 대기합니다.")

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    # 1. 리포트 생성 (생성 후 종료하지 않고 대기)
    if message.content.startswith("!리포트생성"):
        await message.channel.send("🚀 **[Log]** 리포트 생성 프로세스를 시작합니다...")
        
        try:
            await message.channel.send("⏳ **[Log]** 검색 중...")
            
            initial_state = {
                "is_initial_run": True,
                "user_query": "국내 경제 및 금융 산업 일일 브리핑 작성"
            }

            current_config = {
                "configurable": {"thread_id": f"report_thread_{uuid.uuid4().hex[:8]}"},
                "recursion_limit": 15
            }
            
            final_report = ""

            async for output in financial_agent_app.astream(initial_state, config=current_config):
                for node_name, node_state in output.items():
                    
                    if node_name == "agent":
                        latest_message = node_state.get("messages", [])[-1]
                        thought = latest_message.content
                        tool_calls = latest_message.tool_calls
                        
                        if thought:
                            thought_msg = f"🧠 **[에이전트 사고]**\n{thought}"
                            # 1900자씩 잘라서 순차적으로 전송
                            for chunk in [thought_msg[i:i+1900] for i in range(0, len(thought_msg), 1900)]:
                                await message.channel.send(chunk)
                                                
                        if tool_calls:
                            tool_names = [tc['name'] for tc in tool_calls]
                            await message.channel.send(f"🔍 **[도구 호출]** 검색 시작: {', '.join(tool_names)}")

                    elif node_name == "action":
                        await message.channel.send("📥 **[데이터 수집]** 검색 결과를 확보했습니다. 재분석합니다...")
                        
                    elif node_name == "generate_report":
                        await message.channel.send("📝 **[리포트 작성]** 정보 수집이 완료되어 리포트를 작성 중입니다...")
                        final_report = node_state.get("final_report", "")
                        
                    elif node_name == "rag_store":
                        await message.channel.send("💾 **[DB 적재]** 최종 리포트의 노이즈를 제거하고 벡터 DB에 저장했습니다.")
                        
            await message.channel.send("📧 **[Log]** 결과물을 이메일로 발송합니다...")
            
            # [수정 3] 이메일 발송이 디스코드 봇을 멈추게 하지 않도록 비동기 처리
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: send_report_email(report_content=final_report))
            
            await message.channel.send("✅ **[Log]** 발송 완료! 이제 리포트 내용에 대해 질문(RAG)하시거나, 끝내려면 `!종료`를 입력하세요.")
            
        except Exception as e:
            error_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            full_error = traceback.format_exc()
            
            # 컨테이너 내부에 logs 폴더가 없으면 생성
            os.makedirs("logs", exist_ok=True) 
            
            with open("logs/bot_error.log", "a", encoding="utf-8") as f:
                f.write(f"\n[{error_time}] 에러 발생:\n{full_error}\n{'-'*50}")
            
            try:
                await message.channel.send("❌ **[Error Log]** 치명적인 에러가 발생하여 `bot_error.log` 파일에 상세 내역을 기록했습니다.")
                await message.channel.send("🛑 **[Log]** 에러가 발생하여 봇 및 컨테이너를 종료합니다.")
            except Exception as send_e:
                print(f"디스코드 알림 전송 실패: {send_e}")
            
            await client.close() 
        
        return

    # 2. 특정 키워드로 컨테이너 수동 종료
    elif message.content.startswith("!종료"):
        await message.channel.send("🛑 **[Log]** 시스템 종료 명령을 접수했습니다. 봇과 도커 컨테이너를 안전하게 종료합니다. 수고하셨습니다!")
        print("사용자 요청(!종료)에 의해 컨테이너를 종료합니다.")
        await client.close() # 디스코드 연결 종료 -> 파이썬 스크립트 종료 -> 도커 컨테이너 종료
        
        return

    # 3. 일반 채팅 (RAG 챗봇 기능 유지)
    elif message.content and not message.content.startswith("!"):
        async with message.channel.typing():
            try:
                state = {
                    "is_initial_run": False,
                    "user_query": message.content
                }
                
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lambda: financial_agent_app.invoke(state, config=config))
                
                answer = result.get("chat_response")
                
                if not answer:
                    await message.channel.send("⚠️ 에이전트가 답변을 생성하지 못했습니다.")
                    return

                for chunk in [answer[i:i+1900] for i in range(0, len(answer), 1900)]:
                    await message.channel.send(chunk)
                    
            except Exception as e:
                await message.channel.send(f"❌ RAG 처리 중 에러가 발생했습니다: {str(e)}")

if __name__ == "__main__":
    DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    client.run(DISCORD_TOKEN)
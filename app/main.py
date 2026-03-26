import discord
import asyncio
import os
from agent import financial_agent_app, config
from email_sender import send_report_email # 이메일 발송 모듈
from dotenv import load_dotenv

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
                "user_query": "국내 경제 및 은행 산업 일일 브리핑 작성"
            }
            
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: financial_agent_app.invoke(initial_state, config=config))
            
            final_report = result.get("final_report", "")
            
            await message.channel.send("💾 **[Log]** 검색 완료. 벡터 DB에 JSON 구조로 적재되었습니다.")
            await message.channel.send("📧 **[Log]** 결과물을 이메일로 발송합니다...")
            
            send_report_email(report_content=final_report)
            
            # 여기서 종료하지 않고 챗봇 모드로 전환됨을 안내
            await message.channel.send("✅ **[Log]** 발송 완료! 이제 리포트 내용에 대해 질문(RAG)하시거나, 끝내려면 `!종료`를 입력하세요.")
            
        except Exception as e:
            # 에러 발생 시 로그 출력 후 컨테이너 종료 로직 추가
            await message.channel.send(f"❌ **[Error Log]** 에러 발생: {str(e)}")
            await message.channel.send("🛑 **[Log]** 에러가 발생하여 봇 및 컨테이너를 종료합니다.")
            await client.close() # 이 코드가 도커 컨테이너를 종료시킵니다.
        return

    # 2. 특정 키워드로 컨테이너 수동 종료
    if message.content.startswith("!종료"):
        await message.channel.send("🛑 **[Log]** 시스템 종료 명령을 접수했습니다. 봇과 도커 컨테이너를 안전하게 종료합니다. 수고하셨습니다!")
        print("사용자 요청(!종료)에 의해 컨테이너를 종료합니다.")
        await client.close() # 디스코드 연결 종료 -> 파이썬 스크립트 종료 -> 도커 컨테이너 종료
        return

    # 3. 일반 채팅 (RAG 챗봇 기능 유지)
    if message.content:
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
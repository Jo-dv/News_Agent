import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

def send_report_email(report_content):
    print("\n[이메일 전송] 작성된 리포트를 이메일로 발송합니다...")

    SENDER_EMAIL = os.getenv("SENDER_EMAIL")
    SENDER_PASSWORD = os.getenv("SENDER_PASSWORD")
    RECEIVER_EMAIL = os.getenv("RECEIVER_EMAIL")
    
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        print("🚨 [에러] 이메일 계정 정보가 없습니다. .env 파일을 확인해 주세요.")
        return

    today_str = datetime.datetime.now().strftime("%Y년 %m월 %d일")
    subject = f"📊 [금융 인사이트 리포트] {today_str} 핵심 요약"
    
    msg = MIMEMultipart()
    msg['From'] = SENDER_EMAIL
    msg['To'] = RECEIVER_EMAIL if RECEIVER_EMAIL else SENDER_EMAIL
    msg['Subject'] = subject
    
    msg.attach(MIMEText(report_content, 'plain', 'utf-8'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls() # 보안 연결(TLS) 시작
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.send_message(msg)
        server.quit()
        print("이메일 발송이 성공적으로 완료되었습니다!")
    except Exception as e:
        print(f"이메일 발송 실패: {e}")
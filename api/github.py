import http.server
import json
import os
import requests

# Lấy thông tin nhạy cảm từ Environment Variables (Biến môi trường)
# Bạn sẽ cài đặt các biến này trong Vercel sau.
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

class handler(http.server.BaseHTTPRequestHandler):

    def do_POST(self):
        try:
            # 1. Đọc và phân tích dữ liệu JSON từ GitHub
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            payload = json.loads(post_data.decode('utf-8'))

            # 2. Xây dựng tin nhắn dựa trên sự kiện push
            repo_name = payload['repository']['full_name']
            pusher_name = payload['pusher']['name']
            
            # Lấy thông tin các commit
            commit_messages = []
            for commit in payload['commits']:
                # Lấy 50 ký tự đầu của message
                commit_messages.append(f"- `{commit['message'][:50]}`")

            if not commit_messages:
                # Bỏ qua nếu là push trống (ví dụ: tạo branch mới)
                self.send_response(200)
                self.end_headers()
                return

            # Tạo nội dung tin nhắn cuối cùng
            message_text = (
                f"🚀 **New Push** to `{repo_name}` by *{pusher_name}*\n\n"
                f"**Commits:**\n" +
                "\n".join(commit_messages) +
                f"\n\n[View Changes]({payload['compare']})"
            )

            # 3. Gửi tin nhắn đến Telegram
            telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            telegram_payload = {
                'chat_id': CHAT_ID,
                'text': message_text,
                'parse_mode': 'Markdown' # Cho phép định dạng text
            }
            
            response = requests.post(telegram_url, json=telegram_payload)
            response.raise_for_status() # Báo lỗi nếu gửi không thành công

            # 4. Phản hồi thành công cho GitHub
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'status': 'success'}).encode('utf-8'))

        except Exception as e:
            # Ghi lại lỗi và phản hồi lỗi cho GitHub
            print(f"Error: {e}")
            self.send_response(500)
            self.end_headers()

        return
import http.server
import json
import os
import requests

# Lấy thông tin nhạy cảm từ Environment Variables
BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

# --- CÁC HÀM ĐỊNH DẠNG TIN NHẮN CHO TỪNG SỰ KIỆN ---

def format_push_event(payload):
    """Định dạng tin nhắn cho sự kiện push."""
    repo_name = payload['repository']['full_name']
    pusher_name = payload['pusher']['name']
    compare_url = payload['compare']
    
    commits = payload.get('commits', [])
    if not commits:
        return None # Bỏ qua nếu là push trống (ví dụ: tạo/xóa branch)

    commit_messages = []
    for commit in commits:
        # Lấy dòng đầu tiên của commit message
        message = commit['message'].splitlines()[0]
        commit_messages.append(f"- `{message}`")
    
    return (
        f"🚀 **New Push** to `{repo_name}` by *{pusher_name}*\n\n"
        f"**Commits:**\n" +
        "\n".join(commit_messages) +
        f"\n\n[View Changes]({compare_url})"
    )

def format_issues_event(payload):
    """Định dạng tin nhắn cho sự kiện issue."""
    action = payload['action']
    issue = payload['issue']
    repo_name = payload['repository']['full_name']
    sender = payload['sender']['login']
    
    action_emoji = {
        'opened': '🟢', 'closed': '✅', 'reopened': '🔵', 'edited': '✏️'
    }.get(action, '🔔')
    
    return (
        f"{action_emoji} **Issue {action.capitalize()}** in `{repo_name}` by *{sender}*\n\n"
        f"**#{issue['number']}**: {issue['title']}\n"
        f"[View Issue]({issue['html_url']})"
    )

def format_pull_request_event(payload):
    """Định dạng tin nhắn cho sự kiện pull request."""
    action = payload['action']
    pr = payload['pull_request']
    repo_name = payload['repository']['full_name']
    sender = payload['sender']['login']

    if action == 'closed' and pr.get('merged'):
        action_str = 'merged'
        action_emoji = '🎉'
    else:
        action_str = action
        action_emoji = {'opened': '➡️', 'closed': '❌', 'reopened': '🔄'}.get(action, '🔔')

    return (
        f"{action_emoji} **Pull Request {action_str.capitalize()}** in `{repo_name}` by *{sender}*\n\n"
        f"**#{pr['number']}**: {pr['title']}\n"
        f"`{pr['head']['ref']}` → `{pr['base']['ref']}`\n"
        f"[View PR]({pr['html_url']})"
    )

def format_star_event(payload):
    """Định dạng tin nhắn cho sự kiện star."""
    action = payload['action']
    repo_name = payload['repository']['full_name']
    sender = payload['sender']['login']
    star_count = payload['repository']['stargazers_count']
    
    if action == 'created':
        return f"⭐ *{sender}* starred `{repo_name}`! Total stars: **{star_count}**."
    else: # deleted
        return f"⚪️ *{sender}* unstarred `{repo_name}`. Total stars: **{star_count}**."

def format_fork_event(payload):
    """Định dạng tin nhắn cho sự kiện fork."""
    repo_name = payload['repository']['full_name']
    forkee = payload['forkee']
    sender = forkee['owner']['login']
    
    return f"🍴 *{sender}* forked `{repo_name}` to `{forkee['full_name']}`."

def format_generic_event(event, payload):
    """Định dạng tin nhắn cho các sự kiện chưa được hỗ trợ cụ thể."""
    repo_name = payload.get('repository', {}).get('full_name', 'N/A')
    sender = payload.get('sender', {}).get('login', 'N/A')
    action = payload.get('action', '')
    
    return f"🔔 Received event `*{event}*`" + (f" with action `*{action}*`" if action else "") + f" in `{repo_name}` by *{sender}*."

# --- BỘ ĐỊNH TUYẾN SỰ KIỆN ---
EVENT_HANDLERS = {
    "push": format_push_event,
    "issues": format_issues_event,
    "pull_request": format_pull_request_event,
    "star": format_star_event,
    "fork": format_fork_event,
    # Thêm các sự kiện khác vào đây nếu muốn
}

def send_to_telegram(message):
    """Gửi tin nhắn đã định dạng đến Telegram."""
    if not message:
        return
        
    telegram_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    telegram_payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown',
        'disable_web_page_preview': True
    }
    
    try:
        response = requests.post(telegram_url, json=telegram_payload)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Error sending to Telegram: {e}")


class handler(http.server.BaseHTTPRequestHandler):
    """Xử lý các request đến từ webhook của GitHub."""
    def do_POST(self):
        try:
            github_event = self.headers.get('X-GitHub-Event')
            
            if github_event == 'ping':
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"status":"ping_ok"}')
                return

            content_length = int(self.headers['Content-Length'])
            payload = json.loads(self.rfile.read(content_length))
            
            # Lấy hàm xử lý phù hợp, nếu không có thì dùng hàm chung
            formatter = EVENT_HANDLERS.get(github_event, format_generic_event)
            
            if formatter == format_generic_event:
                message = formatter(github_event, payload)
            else:
                message = formatter(payload)

            send_to_telegram(message)
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'{"status":"success"}')

        except Exception as e:
            print(f"Internal Server Error: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b'{"status":"error"}')
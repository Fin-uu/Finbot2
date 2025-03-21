import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from dotenv import load_dotenv

# 載入環境變數
load_dotenv()

app = Flask(__name__)

# LINE Bot設定
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
LINE_CHANNEL_SECRET = os.environ.get('LINE_CHANNEL_SECRET')

# 使用新的v3版本的API設定
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


@app.route("/", methods=['GET'])
def home():
    return "LINE Bot Server is running!"


@app.route("/callback", methods=['POST'])
def callback():
    # 取得X-Line-Signature頭部
    signature = request.headers['X-Line-Signature']

    # 取得請求內容
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # 驗證簽名
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    # 取得使用者傳來的訊息
    user_message = event.message.text
    payer
    user
    # 這裡可以加入您自己的邏輯來處理使用者訊息
    if "哩賀" in user_message:
        reply_text = "你好！很高興認識你！"
    elif "天氣如何" in user_message:
        reply_text = "今天天氣很好！"
    else:
        reply_text = f"你說了：{user_message}"

    # 使用新的v3版本API回覆訊息
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

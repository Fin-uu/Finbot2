import os
import sys
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest,
    TextMessage, QuickReply, QuickReplyItem, MessageAction
)
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

# FinBot 類別實現


class FinBot:
    def __init__(self):
        self.debt_records = {}  # 記錄誰欠誰多少錢
        self.active_users = {}  # 記錄用戶當前狀態
        self.temp_data = {}     # 暫存用戶輸入資料

    def process_message(self, user_id, message):
        """處理用戶訊息並返回回覆"""
        # 初始化新用戶
        if user_id not in self.active_users:
            self.active_users[user_id] = {
                "state": "idle",
                "sub_state": None
            }
            self.temp_data[user_id] = {}

        user_state = self.active_users[user_id]["state"]
        user_sub_state = self.active_users[user_id]["sub_state"]

        # 處理 finbot 命令
        if message.lower() == "finbot" and user_state == "idle":
            self.active_users[user_id]["state"] = "menu"
            return self.show_menu()

        # 處理選單選擇
        if user_state == "menu":
            return self.process_menu_choice(user_id, message)

        # 處理記帳流程
        elif user_state == "add_expense":
            return self.process_add_expense(user_id, message)

        # 處理清帳流程
        elif user_state == "settle_payment":
            return self.process_settle_payment(user_id, message)

    def show_menu(self):
        """顯示主選單（使用按鈕）"""
        text = "請問需要甚麼功能"

        # 使用QuickReply創建按鈕
        quick_reply = QuickReply(
            items=[
                QuickReplyItem(
                    action=MessageAction(
                        label="記帳",
                        text="記帳"
                    )
                ),
                QuickReplyItem(
                    action=MessageAction(
                        label="清帳",
                        text="清帳"
                    )
                ),
                QuickReplyItem(
                    action=MessageAction(
                        label="查帳",
                        text="查帳"
                    )
                ),
                QuickReplyItem(
                    action=MessageAction(
                        label="關閉",
                        text="關閉"
                    )
                )
            ]
        )

        # 返回包含QuickReply的TextMessage
        return {
            "type": "text_with_quick_reply",
            "text": text,
            "quick_reply": quick_reply
        }

    def process_menu_choice(self, user_id, choice):
        """處理選單選擇"""
        if choice == "記帳":
            self.active_users[user_id]["state"] = "add_expense"
            self.active_users[user_id]["sub_state"] = "ask_payer"
            self.temp_data[user_id] = {}
            return "誰付的:"

        elif choice == "清帳":
            self.active_users[user_id]["state"] = "settle_payment"
            self.active_users[user_id]["sub_state"] = "ask_payer"
            self.temp_data[user_id] = {}
            return "誰付:"

        elif choice == "查帳":
            result = self.check_debts()
            return result + "\n" + self.show_menu()

        elif choice == "關閉":
            self.active_users[user_id]["state"] = "idle"
            return "我先下工囉~"

        else:
            return "無效的選擇，請重試\n" + self.show_menu()

    def process_add_expense(self, user_id, message):
        """處理記帳流程"""
        sub_state = self.active_users[user_id]["sub_state"]

        if sub_state == "ask_payer":
            self.temp_data[user_id]["payer"] = message
            self.active_users[user_id]["sub_state"] = "ask_amount"
            return "付多少錢:"

        elif sub_state == "ask_amount":
            try:
                amount = float(message)
                self.temp_data[user_id]["amount"] = amount
                self.active_users[user_id]["sub_state"] = "ask_participants"
                return "有誰分 (用逗號分隔):"
            except ValueError:
                return "金額必須是數字，請重試\n付多少錢:"

        elif sub_state == "ask_participants":
            participants = [name.strip() for name in message.split(",")]
            self.temp_data[user_id]["participants"] = participants

            payer = self.temp_data[user_id]["payer"]
            amount = self.temp_data[user_id]["amount"]

            # 檢查付款人是否也參與分帳
            if payer not in participants:
                self.active_users[user_id]["sub_state"] = "confirm_payer"

                # 使用QuickReply創建 Yes/No 按鈕
                quick_reply = QuickReply(
                    items=[
                        QuickReplyItem(
                            action=MessageAction(
                                label="是 (Y)",
                                text="y"
                            )
                        ),
                        QuickReplyItem(
                            action=MessageAction(
                                label="否 (N)",
                                text="n"
                            )
                        )
                    ]
                )

                return {
                    "type": "text_with_quick_reply",
                    "text": f"付款人 {payer} 是否也參與分帳?",
                    "quick_reply": quick_reply
                }
            else:
                return self.finalize_add_expense(user_id)

        elif sub_state == "confirm_payer":
            if message.lower() == "y":
                self.temp_data[user_id]["participants"].append(
                    self.temp_data[user_id]["payer"])

            return self.finalize_add_expense(user_id)

    def finalize_add_expense(self, user_id):
        """完成記帳流程並計算結果"""
        payer = self.temp_data[user_id]["payer"]
        amount = self.temp_data[user_id]["amount"]
        participants = self.temp_data[user_id]["participants"]

        # 計算每人金額
        per_person = amount / len(participants)

        # 更新債務記錄
        for person in participants:
            if person != payer:
                # 初始化債務記錄
                if person not in self.debt_records:
                    self.debt_records[person] = {}
                if payer not in self.debt_records:
                    self.debt_records[payer] = {}

                # 更新債務 (person 欠 payer)
                if payer not in self.debt_records[person]:
                    self.debt_records[person][payer] = 0
                self.debt_records[person][payer] += per_person

                # 更新互相抵消的債務
                if person in self.debt_records[payer]:
                    # 如果 payer 也欠 person 一些錢，先抵消
                    if self.debt_records[payer][person] >= per_person:
                        self.debt_records[payer][person] -= per_person
                        self.debt_records[person][payer] = 0
                        if self.debt_records[payer][person] == 0:
                            del self.debt_records[payer][person]
                    else:
                        self.debt_records[person][payer] -= self.debt_records[payer][person]
                        del self.debt_records[payer][person]

        # 重置用戶狀態
        self.active_users[user_id]["state"] = "idle"

        # 輸出結果
        result = "===== 已記帳囉! =====\n"
        result += f"付款人: {payer}\n"
        result += f"付款金額: {amount}\n"
        result += f"分帳人員: {', '.join(participants)}\n"
        result += f"每人應付: {per_person:.2f}\n"

        return self.show_menu()

    def process_settle_payment(self, user_id, message):
        """處理清帳流程"""
        sub_state = self.active_users[user_id]["sub_state"]

        if sub_state == "ask_payer":
            self.temp_data[user_id]["payer"] = message
            self.active_users[user_id]["sub_state"] = "ask_receiver"
            return "給誰:"

        elif sub_state == "ask_receiver":
            self.temp_data[user_id]["receiver"] = message
            self.active_users[user_id]["sub_state"] = "ask_amount"
            return "多少錢:"

        elif sub_state == "ask_amount":
            try:
                amount = float(message)
                self.temp_data[user_id]["amount"] = amount

                # 完成清帳
                payer = self.temp_data[user_id]["payer"]
                receiver = self.temp_data[user_id]["receiver"]
                amount = self.temp_data[user_id]["amount"]

                # 更新清帳記錄
                if payer not in self.debt_records:
                    self.debt_records[payer] = {}
                if receiver not in self.debt_records:
                    self.debt_records[receiver] = {}

                if receiver in self.debt_records[payer]:
                    self.debt_records[payer][receiver] -= amount
                    if self.debt_records[payer][receiver] <= 0:
                        del self.debt_records[payer][receiver]

                self.active_users[user_id]["state"] = "idle"
                return "清帳完成！" + "\n" + self.show_menu()

            except ValueError:
                return "金額必須是數字，請重試\n多少錢:"
            
    def check_debts(self):
        """查詢所有債務"""
        if not self.debt_records:
            return "目前沒有任何帳目"

        result = ""
        for debtor, creditors in self.debt_records.items():
            for creditor, amount in creditors.items():
                result += f"{debtor} 欠 {creditor} {amount:.2f}元\n"
        return result


finbot = FinBot()


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    message = event.message.text

    reply = finbot.process_message(user_id, message)

    if isinstance(reply, dict):
        if "quick_reply" in reply:
            quick_reply = reply["quick_reply"]
            text = reply["text"]
            messages = [TextMessage(text=text, quick_reply=quick_reply)]
        else:
            text = reply["text"]
            messages = [TextMessage(text=text)]

    else:
        messages = [TextMessage(text=reply)]

    line_bot_api.reply_message(event.reply_token, messages)


if __name__ == "__main__":
    app.run(debug=True, port=5000)

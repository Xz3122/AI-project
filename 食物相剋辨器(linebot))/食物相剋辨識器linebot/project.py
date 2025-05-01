#匯入LINE BOT SDK、webhook套件
from linebot import (LineBotApi, WebhookHandler)
#匯入Flask套件
from flask import Flask, request, abort
#linebot例外處理
from linebot.exceptions import (InvalidSignatureError)
#匯入linebot.models套件
from linebot.models import *
import os
import io
import configparser
import google.generativeai as genai
#建立臨時文件
import tempfile
#處理圖像專用
from PIL import Image
config = configparser.ConfigParser()
config.read('config.ini')

LINE_CHANNEL_ACCESS_TOKEN = config['LINE']['CHANNEL_ACCESS_TOKEN']
LINE_CHANNEL_SECRET = config['LINE']['CHANNEL_SECRET']
GENAI_API_KEY = config['GENAI']['API_KEY']
PORT = config['SERVER'].getint('PORT')  # 完全從 ini 讀取 port

app = Flask(__name__)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')


#建立一個路由，做為callback
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)
    # handle webhook body
    try:#錯誤回傳400
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    keywords = ["程式", "python", "code", "c++", "java", "coding", "R語言","c#"]#關鍵字用來防止使用者打程式
    user_msg = event.message.text  # 獲取用戶發送的消息
    if any(keyword in user_msg for keyword in keywords):
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="我才不給你打程式咧")
        )
        return  # 終止執行，不發送到gemini
    else:
        user_msg = event.message.text + "利用我回覆你訊息先幫我判斷是否為食物再判斷是食物成分是否有相剋並給出建議，有就回覆我並幫我區分為科學上的相剋和傳統中醫上的相剋"
    
    # 使用 Google Generative AI 生成回應
    response = genai.GenerativeModel(model_name="gemini-1.5-flash").generate_content(user_msg)
    
    # 處理生成的回應文本
    reply_text = response.text.replace("*", "")  
    
    # 回覆用戶的訊息
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    image_id = event.message.id  # 獲取圖片 ID
    image_content = line_bot_api.get_message_content(image_id)  # 下載圖片內容
    
    # 將圖片內容轉換為 BytesIO 對象，以便使用 PIL 處理
    image_bytes = io.BytesIO(image_content.content)
    
    # 使用 Pillow 打開圖片
    message_content = line_bot_api.get_message_content(event.message.id)
    image = Image.open(io.BytesIO(message_content.content))
    # 使用 Gemini 模型生成內容
    response = model.generate_content(["幫我判斷這圖中是否為食物再判斷是否有食物相剋並給出建議，有就回覆我並幫我區分為科學上的相剋和傳統上的相剋",image])
    reply_text = response.text.replace("*", "")
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )

@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
    #使用臨時文件保存音頻
    temp_dir = tempfile.gettempdir()
    temp_audio_path = os.path.join(temp_dir,f'{event.message.id}.m4a')
    try:
        # 取得音檔內容
        message_content = line_bot_api.get_message_content(event.message.id)
        with open(temp_audio_path, 'wb') as fd:
            for chunk in message_content.iter_content():
                fd.write(chunk)
        #設定檔案類型
        mime_type = 'audio/mpeg'
                
        #upload_file方法上傳音檔
        audio = genai.upload_file(temp_audio_path,mime_type = mime_type)
        response = model.generate_content(["幫我判斷語音中是否為食物再判斷是否有食物相剋並給出建議，有就回覆我並幫我區分為科學上的相剋和傳統上的相剋",audio])
        #直接回覆用戶的訊息
        reply_text = response.text.replace("*", "")
        line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_text)
    )
    finally:
        os.remove(temp_audio_path)        

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=PORT, debug=True)
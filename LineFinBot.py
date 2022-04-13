import pandas as pd
import requests
from tokenAccess import TokenAccess
from datetime import datetime, date, time, timedelta
from flask import Flask, request, abort
from linebot import (
    LineBotApi, WebhookHandler
)
from linebot.exceptions import (
    InvalidSignatureError
)
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, QuickReply, QuickReplyButton, MessageAction,
)

app = Flask(__name__)  # 建立Flask物件
accessCode = TokenAccess()

# Line Developers 內的 setting 查詢
line_bot_api = LineBotApi(accessCode.token)
handler = WebhookHandler(accessCode.web)

# Line Message API內中的issue中查詢
@app.route("/callback", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)

def handle_message(event):

    if event.message.text == '@Model A 告訴我推薦的基金':
        text_message = TextSendMessage(text='請選擇基金類別',
                                       quick_reply=QuickReply(items=[
                                           QuickReplyButton(action=MessageAction(label="台灣大型股票", text="@基金-台灣大型股票")),
                                           QuickReplyButton(action=MessageAction(label="全球新興市場股票", text="@基金-全球新興市場股票")),
                                           QuickReplyButton(action=MessageAction(label="中國股票-A股", text="@基金-中國股票-A股"))
                                       ]))
        line_bot_api.reply_message(
            event.reply_token,
            text_message)

    elif '@基金' in event.message.text:
        category = event.message.text.replace('@基金-', '')

        group_ids = {
            '台灣大型股票': 'EUCA000670',
            '全球新興市場股票': 'EUCA000507',
            '中國股票-A股': 'EUCA000896'
        }

        group_id = group_ids[category]
        df = get_bestFunds(group_id)
        message = '{}推薦基金(報酬率 %)'.format(category)

        num = 1

        for index, row in df.head(5).iterrows():
            message += '\n\n第{}名\n{}\n三個月：{}\n六個月：{}\n一年：{}\n三年：{}'.format(num, index,
                                                                           row['三個月'], row['六個月'],
                                                                           row['一年'], row['三年'])
            num += 1

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=message))



    elif '@Model A 告訴我股票損益情況' in event.message.text:

        today = datetime.today() + timedelta(days=-1)
        today = today.strftime('%Y%m%d')
        df = get_daily_prices(today)

        if df is None:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text='今天無收盤價資訊'))
            return None

        期初投入 = 0
        目前損益 = 0

        my_stocks = {
            '0050': 88.00,
            '2308': 210.00,
            '2330': 500.00
        }

        message = '參考{}收盤價 \n您的股票投資組合狀態為:'.format(today)
        for stock_id, buy_price in my_stocks.items():
            current_price = df.loc[stock_id, '收盤價'].item()
            期初投入 += buy_price
            目前損益 += current_price
            message += '\n\n 證券代號：{}\n買入價格為：{} | 目前價格為：{}'.format(stock_id, buy_price, current_price)
        message += '\n\n成本金額：{}\n目前損益：{}\n未實現損益：{}\n報酬率：{}%'.format(
            round(期初投入*1000),
            round(目前損益*1000),
            round((目前損益-期初投入)*1000),
            round(((((目前損益-期初投入)/期初投入))*100), 2)
        )

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=message))

    elif event.message.text == '@Model A 告訴我現在利率':
        text_message = TextSendMessage(text='請選擇幣別', quick_reply=QuickReply(items=[
                                   QuickReplyButton(action=MessageAction(label="美元(USD)", text="@利率-USD")),
                                   QuickReplyButton(action=MessageAction(label="人民幣(CNY)", text="@利率-CNY")),
                                   QuickReplyButton(action=MessageAction(label="澳幣(AUD)", text="@利率-AUD")),
                                   QuickReplyButton(action=MessageAction(label="港幣(HKD)", text="@利率-HKD")),
                                   QuickReplyButton(action=MessageAction(label="新加坡(SGD)", text="@利率-SGD")),
                                   QuickReplyButton(action=MessageAction(label="日圓(JPY)", text="@利率-JPY")),
                                   QuickReplyButton(action=MessageAction(label="歐元(EUR)", text="@利率-EUR")),
                                   QuickReplyButton(action=MessageAction(label="英鎊(GBP)", text="@利率-GBP"))]
                                    ))

        line_bot_api.reply_message(
            event.reply_token,text_message)

    elif '@利率-' in event.message.text:
        currency = event.message.text.replace('@利率-', '')
        df = bestRate(currency)

        message = '最佳{}利率\n'.format(currency)

        for index, row in df.iterrows():
            message += '\n{} | {} | {}'.format(index, row['銀行'][0], row['利率'])

        line_bot_api.reply_message(
            event.reply_token, TextSendMessage(text=message))

    elif event.message.text == '@Model A 告訴我現在匯率':
        text_message = TextSendMessage(text='請選擇幣別', quick_reply=QuickReply(items=[
            QuickReplyButton(action=MessageAction(label="美元(USD)",text="@匯率-美元")),
            QuickReplyButton(action=MessageAction(label="人民幣(CNY)", text="@匯率-人民幣")),
            QuickReplyButton(action=MessageAction(label="澳幣(AUD)", text="@匯率-澳幣")),
            QuickReplyButton(action=MessageAction(label="港幣(HKD)", text="@匯率-港幣")),
            QuickReplyButton(action=MessageAction(label="新加坡幣(SGD)", text="@匯率-新加坡幣")),
            QuickReplyButton(action=MessageAction(label="日圓(JPY)", text="@匯率-日圓")),
            QuickReplyButton(action=MessageAction(label="歐元(EUR)", text="@匯率-歐元")),
            QuickReplyButton(action=MessageAction(label="英鎊(GBP)", text="@匯率-英鎊")),
            QuickReplyButton(action=MessageAction(label="南非幣(ZAR)", text="@匯率-南非幣")),
            QuickReplyButton(action=MessageAction(label="泰銖(THB)", text="@匯率-泰銖")),
            QuickReplyButton(action=MessageAction(label="紐西蘭幣(NZD)", text="@匯率-紐西蘭幣")),
            QuickReplyButton(action=MessageAction(label="加幣(CAD)", text="@匯率-加幣")),
            QuickReplyButton(action=MessageAction(label="瑞士法郎(CHF)", text="@匯率-瑞士法郎")),
        ]))

        line_bot_api.reply_message(event.reply_token, text_message)

    elif "@匯率-" in event.message.text:
        currency = event.message.text.replace('@匯率-', "")

        if currency == '美元':
            currency_ch = 'USD'
        elif currency == '人民幣':
            currency_ch = 'CNY'
        elif currency == '澳幣':
            currency_ch = 'AUD'
        elif currency == '港幣':
            currency_ch = 'HKD'
        elif currency == '新加坡幣':
            currency_ch = 'SGD'
        elif currency == '日圓':
            currency_ch = 'JPY'
        elif currency == '歐元':
            currency_ch = 'EUR'
        elif currency == '英鎊':
            currency_ch = 'GBP'
        elif currency == '瑞士法郎':
            currency_ch = 'CHF'
        elif currency == '加幣':
            currency_ch = 'CAD'
        elif currency == '紐西蘭幣':
            currency_ch = 'NZD'
        elif currency == '泰銖':
            currency_ch = 'THB'
        elif currency == '南非幣':
            currency_ch = 'ZAR'

        df = get_rate(currency, currency_ch)
        message = '{}當前兌台匯率'.format(currency)

        for index, row in df.iterrows():
            message += "\n銀行買入:{} \n銀行賣出:{}".format(row['銀行買入'], row['銀行賣出'])

        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))
    else:
        line_bot_api.reply_message(event.reply_token,TextSendMessage(text=event.message.text))

def get_bestFunds(group_id):
    # 可以把基金url的年和日期拔除 他就會去取得最新的基金資訊
    url = 'https://www.sitca.org.tw/ROC/Industry/IN2422.aspx?txtGROUPID={}'.format(group_id)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    df = pd.read_html(response.text)[7]
    df = df.drop([0, 2], axis=1)  # 刪除兩個columns
    df.columns = df.iloc[1]
    df.drop([0, 1], inplace=True)  # 有inplace 取代的指令 不需在在儲存至df 會空白
    df = df.set_index('基金名稱')
    # df.info() 查詢 Datatype 若是obj則不能sort 所以要改DataType為數值
    df = df.apply(pd.to_numeric, errors='coerce')  # 這樣就會變成float
    # 依照基金績效(長中短)選取與排名
    three_ys = df.sort_values('三年', ascending=False).head(int(len(df) * 0.5))
    one_yrs = three_ys.sort_values('一年', ascending=False).head(int(len(three_ys) * 0.5))
    six_ms = one_yrs.sort_values('六個月', ascending=False).head(int(len(one_yrs) * 0.5))
    three_ms = six_ms.sort_values('三個月', ascending=False).head(int(len(six_ms)))
    return three_ms.sort_values('年化標準差三年(原幣)', ascending=True).head(int(len(three_ms)))

def get_daily_prices(date):
    url = 'https://www.twse.com.tw/exchangeReport/MI_INDEX'
    payload = {
        'response': 'html',
        'date': date,
        'type': 'ALLBUT0999'
    }
    headers = {
        'user-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    }
    response = requests.get(url, params=payload, headers=headers)

    try:  # 用try and except 找出表格如果沒有就return None (表示沒有)
        df = pd.read_html(response.text)[-1]
    except:
        return None

    df.columns = df.columns.get_level_values(2)
    df.drop(['證券名稱', '漲跌(+/-)'], axis=1, inplace=True)
    df.set_index(['證券代號'], inplace=True)
    df = df.apply(pd.to_numeric, errors='coerce')
    df.drop(df[df['收盤價'].isnull()].index, inplace=True)
    return df

def Esun_deposit_forex():
    url = 'https://www.esunbank.com.tw/bank/personal/deposit/rate/foreign/deposit-rate'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    response.text
    df = pd.read_html(response.text)[0]
    df = df.drop([0, 1])  # 丟掉前面兩行
    df.columns = ['幣別', '活期', '一週', '二週', '三週', '一個月', '三個月', '六個月', '九個月', '一年']
    # 重新設定欄位名稱
    df['幣別'] = df['幣別'].str.extract('([A-Z]+)')
    df['銀行'] = '玉山銀行'
    df = df.set_index(['銀行', '幣別'])
    df = df.apply(pd.to_numeric, errors='coerce')
    return df

def TaiwanBank_deposit():
    url = 'https://rate.bot.com.tw/ir?Lang=zh-TW'
    headers = {
        'User-Agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    response.text
    df = pd.read_html(response.text)[0]
    df = df.drop(df.columns[[-1, -2]], axis=1)  # 刪除多重欄位要包兩層
    df.columns = ['幣別', '活期', '一週', '二週', '三週', '一個月', '三個月', '六個月', '九個月', '一年']
    df.drop(1)
    df['幣別'] = df['幣別'].str.extract('([A-Z]+)')  # 汲取字串 要包一層括號
    df['銀行'] = '台灣銀行'
    df = df.set_index(['銀行', '幣別'])
    df = df.apply(pd.to_numeric, errors='coerce')
    return df

def bestRate(currency):
    玉山 = Esun_deposit_forex()
    台銀 = TaiwanBank_deposit()
    bank = pd.concat([玉山, 台銀], sort=False)
    bank = bank[['活期', '一週', '二週', '三週', '一個月', '三個月', '六個月', '九個月', '一年']]
    rate = bank[bank.index.get_level_values('幣別') == currency]
    highestUSDRate = pd.DataFrame({
        '銀行': rate.idxmax(),
        '利率': rate.max()
    })
    return highestUSDRate

def Esun_Rate():
    url = 'https://www.esunbank.com.tw/bank/personal/deposit/rate/forex/foreign-exchange-rates'
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/87.0.4280.88 Safari/537.36'
    }
    response = requests.get(url, headers=headers)
    df = pd.read_html(response.text)[0]
    df = df.drop(df.columns[[3,4,5,6]], axis=1)
    df.columns = ['幣別','銀行買入','銀行賣出']
    df['銀行'] = '玉山銀行'
    df = df.set_index(['銀行', '幣別'])
    df = df.apply(pd.to_numeric, errors='coerce')
    return df

def get_rate(currency, currency_ch):
    df = Esun_Rate()
    dfCurrency = df[df.index.get_level_values('幣別')=='{}({})'.format(currency, currency_ch)]
    return dfCurrency

if __name__ == "__main__":
    app.run()

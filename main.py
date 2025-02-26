from wxauto import WeChat
import time
from database import Database

wx = WeChat()
listen_list = ['李东远']

for i in listen_list:
    wx.AddListenChat(who=i, savepic=True)

while True:
    msgs = wx.GetListenMessage()
    for chat in msgs:
        who = chat.who  # 获取聊天窗口名（人或群名）
        one_msgs = msgs.get(chat)  # 获取消息内容
        # 回复收到
        for msg in one_msgs:
            msgtype = msg.type  # 获取消息类型
            content = msg.content  # 获取消息内容，字符串类型的消息内容
            print(f'【{who}】：{content}')
            # ===================================================
            # 处理消息逻辑（如果有）
            #
            # 处理消息内容的逻辑每个人都不同，按自己想法写就好了，这里不写了
            #
            # ===================================================

            if msgtype == 'friend':
                try:
                    # 解析消息内容,支持多种分隔符
                    content = content.replace('，', ',').replace('/', ',').replace(' ', ',').strip()
                    parts = content.split(',')
                    # 过滤空字符串并获取有效部分
                    parts = [p.strip() for p in parts if p.strip()]

                    if len(parts) != 3:
                        chat.SendMsg('写入失败:格式错误,请使用"名称,数量,价格"格式(支持逗号/空格/斜杠分隔)')
                        continue

                    name = parts[0]
                    number = float(parts[1])
                    prace = float(parts[2])

                    # 发送确认信息
                    confirm_msg = f'请确认以下信息:\n名称: {name}\n数量: {number}\n价格: {prace}\n\n回复"确认"或"1"确认写入,回复"不确认"或"0"取消'
                    chat.SendMsg(confirm_msg)

                    # 等待用户确认
                    time.sleep(15)  # 等待30秒获取回复
                    confirm_msgs = wx.GetListenMessage()
                    should_write = True  # 默认30秒无回复时写入

                    # 检查确认回复
                    for confirm_chat in confirm_msgs:
                        if confirm_chat.who == who:
                            has_reply = True
                            confirm_content = confirm_msgs.get(confirm_chat)[-1].content
                            # 检查否定回复
                            if confirm_content in ['不确认', '0']:
                                should_write = False
                                chat.SendMsg('已取消本次写入')
                                break
                            # 检查肯定回复
                            elif confirm_content in ['确认', '1']:
                                should_write = True
                                break

                    # 写入数据库
                    db = Database()
                    if should_write:
                        db.insert_data(name, number, prace)
                        if confirm_content in ['确认', '1', 'yes', 'ok', '是', '好', '好的', '可以']:
                            chat.SendMsg('已确认并写入数据库')
                        else:
                            chat.SendMsg('30秒内未收到回复,已自动写入数据库')

                    # 获取并发送数据总结
                    all_data = db.get_all_data()
                    total_rows = len(all_data)
                    total_number = sum(row[2] for row in all_data)  # number在第3列
                    total_value = sum(row[2] * row[3] for row in all_data)  # 数量*价格

                    summary = f'数据库统计:\n总记录数: {total_rows}\n商品总数量: {total_number:.2f}\n商品总金额: {total_value:.2f}'
                    chat.SendMsg(summary)

                    db.close()
                except Exception as e:
                    chat.SendMsg(f'写入失败:{str(e)}')

    time.sleep(0.5)
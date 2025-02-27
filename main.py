import sqlite3
import time
import datetime
import os
import re
import threading
import pandas as pd
from wxauto import WeChat

# 消息处理类
class MessageProcessor:
    def __init__(self):
        """初始化消息处理器"""
        self.pending_data = {}  # 存储待确认的数据 {who: (table_name, data_dict)}
        self.confirmation_timers = {}  # 存储确认计时器 {who: timer}
        self.last_operations = {}  # 存储最后操作记录 {who: {table, id}}
    
    def ensure_database_exists(self, friend_name):
        """确保好友数据库和必要的表存在"""
        db_path = f"{friend_name}.db"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 创建测试表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS test (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                content TEXT
            )
            ''')
            
            # 创建交易表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS trade (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT DEFAULT "trade.db",
                date TEXT,
                name TEXT,
                type INTEGER DEFAULT 0,
                direction INTEGER DEFAULT 1,
                number REAL,
                price REAL,
                link TEXT DEFAULT "无"
            )
            ''')
            
            # 创建日记/笔记表
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS note (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT DEFAULT "note.db",
                date TEXT,
                name TEXT,
                note TEXT
            )
            ''')
            
            conn.commit()
            conn.close()
            print(f"已确保数据库 {db_path} 存在并包含所需表")
            return True
        except Exception as e:
            print(f"创建数据库 {db_path} 失败: {str(e)}")
            return False
    
    def message_process(self, who, content):
        """处理消息内容，解析为结构化数据"""
        # 替换各种分隔符为标准逗号
        content = re.sub(r'[,，\s/]+', ',', content.strip())
        parts = [p.strip() for p in content.split(',') if p.strip()]
        
        # 根据数据长度选择数据库表
        if len(parts) >= 6 and len(parts) <= 8:
            # 交易信息格式: 名称,类型,方向,数量,价格,链接
            try:
                data = {
                    'table_name': 'trade.db',
                    'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'name': parts[0],
                    'type': int(parts[1]) if len(parts) > 1 else 0,
                    'direction': int(parts[2]) if len(parts) > 2 else 1,
                    'number': float(parts[3]) if len(parts) > 3 else 0,
                    'price': float(parts[4]) if len(parts) > 4 else 0,
                    'link': parts[5] if len(parts) > 5 else "无"
                }
                
                self.pending_data[who] = ("trade", data)
                
                # 构建确认消息
                type_str = "合约" if data['type'] == 1 else "现货"
                direction_str = "买入" if data['direction'] == 1 else "卖出"
                
                confirm_msg = f"请确认以下交易信息:\n"
                confirm_msg += f"名称: {data['name']}\n"
                confirm_msg += f"类型: {type_str}\n"
                confirm_msg += f"方向: {direction_str}\n"
                confirm_msg += f"数量: {data['number']}\n"
                confirm_msg += f"价格: {data['price']}\n"
                confirm_msg += f"链接: {data['link']}\n\n"
                confirm_msg += "回复'确认'或'1'确认写入，回复'不确认'或'0'取消"
                
                return confirm_msg
                
            except Exception as e:
                return f"解析交易数据失败: {str(e)}\n正确格式: 名称,类型(0/1),方向(0/1),数量,价格,链接"
                
        elif len(parts) >= 3 and len(parts) <= 4:
            # 笔记信息格式: 名称,内容
            try:
                data = {
                    'table_name': 'note.db',
                    'date': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'name': parts[0],
                    'note': parts[1] if len(parts) > 1 else ""
                }
                
                self.pending_data[who] = ("note", data)
                
                confirm_msg = f"请确认以下笔记信息:\n"
                confirm_msg += f"名称: {data['name']}\n"
                confirm_msg += f"内容: {data['note']}\n\n"
                confirm_msg += "回复'确认'或'1'确认写入，回复'不确认'或'0'取消"
                
                return confirm_msg
                
            except Exception as e:
                return f"解析笔记数据失败: {str(e)}\n正确格式: 名称,内容"
        
        else:
            return ("无法识别的数据格式。\n"
                    "交易数据格式(6-8项): 名称,类型(0/1),方向(0/1),数量,价格,链接\n"
                    "笔记数据格式(3-4项): 名称,内容")
    
    def start_confirmation_timer(self, who, chat):
        """启动确认计时器"""
        # 取消已存在的计时器
        if who in self.confirmation_timers and self.confirmation_timers[who].is_alive():
            self.confirmation_timers[who].cancel()
        
        # 创建新计时器
        timer = threading.Timer(15.0, self.auto_confirm, args=[who, chat])
        timer.daemon = True
        timer.start()
        self.confirmation_timers[who] = timer
        print(f"已为 {who} 启动15秒确认计时器")
    
    def auto_confirm(self, who, chat):
        """自动确认并保存数据"""
        if who in self.pending_data:
            result = self.save_to_database(who)
            try:
                chat.SendMsg(f"15秒内未收到回复，已自动确认写入数据库\n{result}")
                print(f"已为 {who} 自动确认并保存数据")
            except Exception as e:
                print(f"发送自动确认消息给 {who} 失败: {str(e)}")
    
    def process_confirmation(self, who, content):
        """处理用户确认消息"""
        # 取消计时器
        if who in self.confirmation_timers and self.confirmation_timers[who].is_alive():
            self.confirmation_timers[who].cancel()
            print(f"已取消 {who} 的确认计时器")
        
        if content.lower() in ["确认", "1"]:
            result = self.save_to_database(who)
            return f"已确认并写入数据库\n{result}"
        elif content.lower() in ["不确认", "0"]:
            if who in self.pending_data:
                del self.pending_data[who]
                print(f"{who} 已取消确认")
            return "已取消本次写入"
        else:
            return "未识别的确认指令，请回复'确认'/'1'或'不确认'/'0'"
    
    def save_to_database(self, who):
        """将待处理数据保存到数据库"""
        if who not in self.pending_data:
            return "没有待确认的数据"
        
        table_name, data = self.pending_data[who]
        db_path = f"{who}.db"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            if table_name == "trade":
                cursor.execute('''
                INSERT INTO trade (table_name, date, name, type, direction, number, price, link)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data['table_name'],
                    data['date'],
                    data['name'],
                    data['type'],
                    data['direction'],
                    data['number'],
                    data['price'],
                    data['link']
                ))
            elif table_name == "note":
                cursor.execute('''
                INSERT INTO note (table_name, date, name, note)
                VALUES (?, ?, ?, ?)
                ''', (
                    data['table_name'],
                    data['date'],
                    data['name'],
                    data['note']
                ))
            
            conn.commit()
            last_id = cursor.lastrowid
            conn.close()
            
            # 记录最后操作
            self.last_operations[who] = {
                'table': table_name,
                'id': last_id
            }
            
            print(f"已将数据保存到 {who} 的 {table_name} 表，ID: {last_id}")
            
            # 清除待确认数据
            del self.pending_data[who]
            
            # 返回数据统计信息
            return self.get_statistics(who)
            
        except Exception as e:
            print(f"保存数据到 {who} 的数据库失败: {str(e)}")
            return f"保存数据失败: {str(e)}"
    
    def get_statistics(self, who, detailed=False):
        """获取好友数据库的统计信息"""
        db_path = f"{who}.db"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # 基本统计
            trade_count = cursor.execute("SELECT COUNT(*) FROM trade").fetchone()[0]
            note_count = cursor.execute("SELECT COUNT(*) FROM note").fetchone()[0]
            
            stats = f"数据统计 - {who}:\n"
            stats += f"- 交易记录: {trade_count} 条\n"
            stats += f"- 笔记记录: {note_count} 条\n"
            
            # 交易统计
            if trade_count > 0:
                # 交易总额
                cursor.execute("SELECT SUM(number * price) FROM trade")
                total_value = cursor.fetchone()[0] or 0
                stats += f"- 交易总金额: {total_value:.2f}\n"
                
                # 买入/卖出统计
                cursor.execute("SELECT COUNT(*) FROM trade WHERE direction = 1")
                buy_count = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM trade WHERE direction = 0")
                sell_count = cursor.fetchone()[0]
                stats += f"- 买入交易: {buy_count} 条\n"
                stats += f"- 卖出交易: {sell_count} 条\n"
            
            # 详细统计
            if detailed and trade_count > 0:
                try:
                    # 使用pandas进行更复杂的分析
                    df = pd.read_sql_query("SELECT * FROM trade", conn)
                    
                    # 按类型统计
                    type_counts = df['type'].value_counts()
                    stats += f"\n按类型统计:\n"
                    stats += f"- 现货交易: {type_counts.get(0, 0)} 条\n"
                    stats += f"- 合约交易: {type_counts.get(1, 0)} 条\n"
                    
                    # 最近交易统计
                    stats += f"\n最近5条交易:\n"
                    recent = df.sort_values('date', ascending=False).head(5)
                    for i, row in recent.iterrows():
                        type_str = "合约" if row['type'] == 1 else "现货"
                        dir_str = "买入" if row['direction'] == 1 else "卖出"
                        stats += f"- {row['date']}: {row['name']} {type_str} {dir_str} {row['number']}个 价格:{row['price']}\n"
                except Exception as e:
                    stats += f"\n获取详细统计失败: {str(e)}"
                
            conn.close()
            return stats
            
        except Exception as e:
            print(f"获取 {who} 的统计信息失败: {str(e)}")
            return f"获取统计信息失败: {str(e)}"
    
    def delete_last_record(self, who):
        """删除好友最后一条记录"""
        if who not in self.last_operations:
            return "没有可删除的记录"
        
        table = self.last_operations[who]['table']
        record_id = self.last_operations[who]['id']
        db_path = f"{who}.db"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
            
            if cursor.rowcount > 0:
                conn.commit()
                conn.close()
                print(f"已删除 {who} 的最后一条记录 (表:{table}, ID:{record_id})")
                del self.last_operations[who]
                return f"已删除最后一条 {table} 记录"
            else:
                conn.close()
                return f"未找到要删除的记录"
                
        except Exception as e:
            print(f"删除 {who} 的记录失败: {str(e)}")
            return f"删除记录失败: {str(e)}"

# 主程序
def main():
    """主程序入口"""
    try:
        print("正在初始化微信自动化...")
        wx = WeChat()
        processor = MessageProcessor()
        
        # 需要监听的好友列表
        listen_list = ['李东远', '文件传输助手']
        active_friends = []
        
        print("正在初始化数据库...")
        for friend in listen_list:
            processor.ensure_database_exists(friend)
        
        print("正在设置微信监听...")
        for friend in listen_list:
            try:
                print(f"尝试添加监听好友: {friend}")
                # 先尝试打开聊天窗口
                wx.ChatWith(friend)
                time.sleep(1)  # 等待窗口加载
                wx.AddListenChat(who=friend, savepic=True)
                active_friends.append(friend)
                print(f"成功添加监听好友: {friend}")
            except Exception as e:
                print(f"无法添加监听好友 {friend}: {str(e)}")
        
        if not active_friends:
            print("警告: 没有成功添加任何监听好友，程序将退出")
            return
        
        print(f"成功监听的好友: {', '.join(active_friends)}")
        print("程序已启动，正在监听消息...")
        
        while True:
            try:
                msgs = wx.GetListenMessage()
                for chat in msgs:
                    who = chat.who  # 聊天窗口名（好友名）
                    one_msgs = msgs.get(chat)  # 获取消息内容
                    
                    for msg in one_msgs:
                        msgtype = msg.type  # 消息类型
                        content = msg.content  # 消息内容
                        print(f'收到消息【{who}】：{content}')
                        
                        # 只处理好友消息
                        if msgtype == 'friend':
                            # 处理删除最后一条记录命令
                            if content == '-1':
                                result = processor.delete_last_record(who)
                                chat.SendMsg(result)
                                continue
                            
                            # 处理查看更多统计信息命令
                            if content.lower() in ['统计', 'stats', '查看统计']:
                                result = processor.get_statistics(who, detailed=True)
                                chat.SendMsg(result)
                                continue
                            
                            # 处理确认/不确认命令
                            if who in processor.pending_data and content.lower() in ['确认', '1', '不确认', '0']:
                                result = processor.process_confirmation(who, content)
                                chat.SendMsg(result)
                                continue
                            
                            # 处理普通消息，尝试解析数据
                            result = processor.message_process(who, content)
                            chat.SendMsg(result)
                            
                            # 启动确认计时器
                            if who in processor.pending_data:
                                processor.start_confirmation_timer(who, chat)
            
            except KeyboardInterrupt:
                print("程序被用户中断，正在退出...")
                break
            except Exception as e:
                print(f"处理消息时发生错误: {str(e)}")
                print("5秒后重试...")
                time.sleep(5)
            
            time.sleep(0.5)
    
    except Exception as e:
        print(f"程序初始化失败: {str(e)}")

if __name__ == "__main__":
    main()
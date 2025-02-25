import sqlite3
from datetime import datetime

class Database:
    def __init__(self, db_name='test.db'):
        """初始化数据库连接"""
        self.db_name = db_name
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_table()
    
    def create_table(self):
        """创建test0表"""
        create_table_sql = '''
        CREATE TABLE IF NOT EXISTS test0 (
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            name TEXT,
            number DECIMAL(10,2),
            prace DECIMAL(10,2)
        )
        '''
        self.cursor.execute(create_table_sql)
        self.conn.commit()
    
    def insert_data(self, name, number, prace):
        """插入数据"""
        insert_sql = '''
        INSERT INTO test0 (name, number, prace)
        VALUES (?, ?, ?)
        '''
        self.cursor.execute(insert_sql, (name, number, prace))
        self.conn.commit()
    
    def get_all_data(self):
        """获取所有数据"""
        self.cursor.execute('SELECT * FROM test0')
        return self.cursor.fetchall()
    
    def close(self):
        """关闭数据库连接"""
        self.conn.close()


import random
from telegram import Bot, Update
from telegram.ext import *
from datetime import datetime, timedelta
from pytz import timezone
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
import threading
import time
import sqlite3
import asyncio
import atexit


pool_size = 100000
connect_timeout = 300

# 텔레그램 봇 인스턴스 생성
bot_token = ''
application = (Application.builder().token(bot_token)
               .get_updates_connection_pool_size(pool_size)
               .get_updates_connect_timeout(connect_timeout)
               .read_timeout(300).get_updates_read_timeout(300)
               .write_timeout(300).get_updates_write_timeout(300)
               .build())
bot = application.bot


# 허용된 그룹 ID 리스트
# 여기에 허용하려는 그룹의 ID들을 적어주세요.
allowed_group_ids = []


async def add_user(username, user_id, initial_coins, full_name):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()

    # Check if user exists
    cursor.execute("SELECT * FROM Users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        # Default values
        current_date_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Insert new user
        cursor.execute("""
            INSERT INTO Users (user_id, username, coins, last_attendance_check, full_name)
            VALUES (?, ?, ?, ?, ?)
        """, (user_id, username, initial_coins, None, full_name))
    else:
        # Update full_name for existing user
        cursor.execute("UPDATE Users SET full_name = ? WHERE user_id = ?", (full_name, user_id))
        conn.commit()

    conn.commit()  # Commit the transaction
    conn.close()


def create_database():
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            coins INTEGER,
            last_attendance_check DATETIME DEFAULT NULL,
            attendance_counts INTEGER DEFAULT 0,
            full_name TEXT,
            winnings INTEGER DEFAULT 0,
            loses INTEGER DEFAULT 0,
            draws INTEGER DEFAULT 0
        )
        """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS Bets (
            user_id INTEGER,
            amount INTEGER,
            bet_type TEXT,
            odds REAL
        )
        """)

    conn.commit()
    conn.close()


create_database()


# Initialize the user_coins dictionary at the start of the program.
async def initialize_user_coins():
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, coins FROM users')
    rows = cursor.fetchall()

    global user_coins
    user_coins = {row[0]: row[1] for row in rows}


async def auto_save_db(user_coins):
    # user_coins 딕셔너리의 내용을 user_coins 테이블에 저장
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    for user_id, coins in user_coins.items():
        cursor.execute('''
            INSERT OR REPLACE INTO user_coins (user_id, coins)
            VALUES (?, ?)
        ''', (user_id, coins))
    conn.commit()


# 기존 코드 시작...
game_in_progress = False

game_in_progress = False 


# 스티커 파일 아이디 리스트
stickers = ["CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA", 
            "CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA",
              "CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA",
              'CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA',
              'CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA',
              'CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA',
              'CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA',
              'CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E',
              'CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ',
              'CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA',
              'CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA',
              'CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA',
              'CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA',
              'CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA',
              'CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA',
              'CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA',
              'CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA',
              'CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA',
              'CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ',
              'CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA'
]
# 각 스티커 조합의 점수 정의
sticker_combination_scores = {("CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA", "CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA"): {"score": 98, "name": "광땡"},
    ("CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA", "CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA"): {"score": 98, "name": "광땡"},
    ('CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA', 'CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'): {"score": 99, "name": "38광땡"},
    ('CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA', 'CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA'): {"score": 99, "name": "38광땡"},
    ('CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'): {"score": 98, "name": "광땡"},
    ('CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA','CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA'): {"score": 98, "name": "광땡"},
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ'): {"score": 97, "name": "장땡"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA'): {"score": 97, "name": "장땡"},
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA'): {"score": 96, "name": "구땡"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA'): {"score": 96, "name": "구땡"},
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA'): {"score": 95, "name": "팔땡"},
    ('CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA','CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA'): {"score": 94, "name": "칠땡"},
    ('CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA','CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA'): {"score": 93, "name": "육땡"},
    ('CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA','CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ'): {"score": 92, "name": "오땡"},
    ('CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'): {"score": 91, "name": "사땡"},
    ('CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'): {"score": 90, "name": "삼땡"},
    ('CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'): {"score": 89, "name": "이땡"},
    ('CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA','CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA'): {"score": 88, "name": "일땡"},
    ('CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 80, "name": "알리"},
    ('CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 80, "name": "알리"},
    ('CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 80, "name": "알리"},
    ('CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 80, "name": "알리"},
    ('CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 70, "name": "독사"},
    ('CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 70, "name": "독사"},
    ('CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 70, "name": "독사"},
    ('CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 70, "name": "독사"},
    ('CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA','CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA'):{"score": 60, "name": "구삥"},
    ('CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA','CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA'):{"score": 60, "name": "구삥"},
    ('CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA','CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA'):{"score": 60, "name": "구삥"},
    ('CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA','CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA'):{"score": 60, "name": "구삥"},
    ('CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA','CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ'):{"score": 50, "name": "장삥"},
    ('CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA','CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA'):{"score": 50, "name": "장삥"},
    ('CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA','CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ'):{"score": 50, "name": "장삥"},
    ('CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA','CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA'):{"score": 50, "name": "장삥"},
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 40, "name": "장사"},
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 40, "name": "장사"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 40, "name": "장사"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 40, "name": "장사"},
    ('CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA','CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA'):{"score": 30, "name": "세륙"},
    ('CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA','CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA'):{"score": 30, "name": "세륙"},
    ('CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E','CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA'):{"score": 30, "name": "세륙"},
    ('CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E','CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA'):{"score": 30, "name": "세륙"},
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA'):{"score": 9, "name": "갑오"}, #10 9
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA'):{"score": 9, "name": "갑오"}, #8 1
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA','CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 9, "name": "갑오"}, # 7 2
    ('CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'):{"score": 9, "name": "갑오"}, # 6 3
    ('CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 9, "name": "갑오"}, # 5 4
    ('CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 9, "name": "갑오"},
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA'):{"score": 8, "name": "여덟끗"}, # 10 8
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA','CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA'):{"score": 8, "name": "여덟끗"}, # 7 1
    ('CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA','CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA','CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA','CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 8, "name": "여덟끗"}, #6 2
    ('CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 8, "name": "여덟끗"}, # 5 3
    ('CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'):{"score": 8, "name": "여덟끗"},
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA'):{"score": 7, "name": "일곱끗"}, # 10 7
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA','CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA'):{"score": 7, "name": "일곱끗"}, # 6 1
    ('CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA','CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA','CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA','CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 7, "name": "일곱끗"}, # 5 2
    ('CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 7, "name": "일곱끗"}, # 4 3
    ('CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA'):{"score": 7, "name": "일곱끗"}, # 9 8
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA'):{"score": 7, "name": "일곱끗"},
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA'):{"score": 6, "name": "여섯끗"}, # 10 6
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA','CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA'):{"score": 6, "name": "여섯끗"}, # 5 1
    ('CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA','CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ','CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ','CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA'):{"score": 6, "name": "여섯끗"}, # 9 7
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 6, "name": "여섯끗"}, # 4 2
    ('CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 6, "name": "여섯끗"},
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA'):{"score": 5, "name": "다섯끗"}, # 10 5
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA'):{"score": 5, "name": "다섯끗"}, #9 6
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA'):{"score": 5, "name": "다섯끗"}, # 8 7
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA','CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA','CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 5, "name": "다섯끗"}, # 3 2
    ('CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 5, "name": "다섯끗"},
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA'):{"score": 4, "name": "네끗"}, # 9 5
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ'):{"score": 4, "name": "네끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA'):{"score": 4, "name": "네끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ'):{"score": 4, "name": "네끗"},
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA'):{"score": 4, "name": "네끗"}, # 8 6
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA'):{"score": 4, "name": "네끗"},
    ('CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA','CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA'):{"score": 4, "name": "네끗"},
    ('CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA','CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA'):{"score": 4, "name": "네끗"},
    ('CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA','CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA'):{"score": 4, "name": "네끗"}, # 3 1
    ('CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA','CAACAgUAAxkBAANtZKFDAZDwqQdXGnasETOmq-BLjSQAAkEKAALzPRFV1frRtVXqgL4vBA'):{"score": 4, "name": "네끗"},
    ('CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA','CAACAgUAAxkBAANuZKFDFAcsyh4srBj6Qx5LQEEW90EAAkcMAALsBRBVrFDy6PO8eJ0vBA'):{"score": 4, "name": "네끗"},
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 3, "name": "세끗"}, # 10 3
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'):{"score": 3, "name": "세끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 3, "name": "세끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'):{"score": 3, "name": "세끗"},
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 3, "name": "구사"},  # 9 4
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 3, "name": "구사"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 3, "name": "구사"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 3, "name": "구사"},
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA'):{"score": 3, "name": "세끗"}, # 8 5
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ'):{"score": 3, "name": "세끗"},
    ('CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA','CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA'):{"score": 3, "name": "세끗"},
    ('CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA','CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ'):{"score": 3, "name": "세끗"},
    ('CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA','CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA'):{"score": 3, "name": "세끗"}, # 7 6
    ('CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA','CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA'):{"score": 3, "name": "세끗"},
    ('CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA','CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA'):{"score": 3, "name": "세끗"},
    ('CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA','CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA'):{"score": 3, "name": "세끗"},
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 2, "name": "두끗"}, # 10 2
    ('CAACAgUAAxkBAAOAZKFDJgaoR8gda0t-E8gse85--mUAApsLAAIlIghVeLQwQSOTWTYvBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN_ZKFDJR6jvR88SQwE_bI8L2JeBqkAAj4JAAJJ-hFVmifE58H6AAF1LwQ','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 2, "name": "두끗"}, # 9 3
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 2, "name": "두끗"}, # 8 4
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA','CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA'):{"score": 2, "name": "두끗"}, # 7 5
    ('CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA','CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA','CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA','CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ'):{"score": 2, "name": "두끗"},
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 1, "name": "한끗"}, # 9 2
    ('CAACAgUAAxkBAAN-ZKFDJGx6L2B7wBNtMEMqiC9fb4EAAjQLAAKPGwlVN_-DaTWHa4ovBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 2, "name": "한끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAANwZKFDGGL2Zcnb2fv7MAHoO49MBJ4AAiEKAAKosAlVeKbbGxotq6AvBA'):{"score": 1, "name": "한끗"},
    ('CAACAgUAAxkBAAN9ZKFDIwLgOHZntsIx6wMSPbctRvkAAkwKAAJzhxBVNIskDM89Z08vBA','CAACAgUAAxkBAANvZKFDF60GrQ4g0E5BCiy7H21YH1QAAqgMAAI2SwlVqRY2-UBKJWcvBA'):{"score": 1, "name": "한끗"},
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 1, "name": "한끗"}, # 8 3
    ('CAACAgUAAxkBAAN8ZKFDI5OmT9Fl-KU0eQm3iWLowLcAApANAALtlwlV_s88dGXSmFAvBA','CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA'):{"score": 1, "name": "한끗"},
    ('CAACAgUAAxkBAAN7ZKFDIiKj4AyLaYLQw1xUklVFb8QAAscLAAId1glV5AEfymqtjwovBA','CAACAgUAAxkBAANyZKFDG29K9AeE63ydtG-PCn3qX6YAArcJAAITEghV9GYvQtbo7x8vBA'):{"score": 1, "name": "한끗"},
    ('CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 1, "name": "한끗"}, # 7 4
    ('CAACAgUAAxkBAAN6ZKFDIdM5sD_6VXZlmP4PB3ktVkMAAvAKAAIR7whVqij8CJnkw-QvBA','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 1, "name": "한끗"},
    ('CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA','CAACAgUAAxkBAAN0ZKFDHNQnBah35yhDPBeMS--FngADggsAAslfCVWoArRK-WnvZS8E'):{"score": 1, "name": "한끗"},
    ('CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA','CAACAgUAAxkBAANzZKFDG0s_jCHrt7rpigWdLv3Ew_sAAjkKAAJiyAlVM0ChKU3e71AvBA'):{"score": 1, "name": "암행어사"},
    ('CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA','CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA'):{"score": 1, "name": "한끗"}, # 6 5
    ('CAACAgUAAxkBAAN4ZKFDIKO6qtAdt723_ZtwIg8nEDgAAsEKAAJJ-AhV8FY931eEMKwvBA','CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ'):{"score": 1, "name": "한끗"},
    ('CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA','CAACAgUAAxkBAAN2ZKFDHjh6XZJYT-XeCsn0jQ3yEcQAAvkJAAIbTxFVhhXx0BJ9uwUvBA'):{"score": 1, "name": "한끗"},
    ('CAACAgUAAxkBAAN3ZKFDH5viWfgJ5RF_v5Q4Qi_bVVQAApQJAALvEAhVaoMt81ohWy0vBA','CAACAgUAAxkBAAN1ZKFDHYO2t_LdAAHBYeYLtLN1tuBsAAJmCwAC7l4QVcDpyHbl0X7RLwQ'):{"score": 1, "name": "한끗"},
    ('CAACAgUAAxkBAANxZKFDGiJDmPU726bgL7rguzZ7xl0AAm0LAAICHwhV9kQKUUFqXikvBA','CAACAgUAAxkBAAN5ZKFDICzuRnwXcvpLmP8ndTYmGvoAAkEKAAJd2RFV4_AKF09HQrUvBA'):{"score": 0, "name": "땡잡이"},


}

sorted_scores = {}

for combination, score in sticker_combination_scores.items():
    sorted_combination = tuple(sorted(combination))
    if sorted_combination not in sorted_scores:
        sorted_scores[sorted_combination] = score


special_rules = [("암행어사", "광땡"),("땡잡이", "구땡","팔땡","칠땡","육땡","오땡","사땡","삼땡","이땡","일땡")]



# 특별한 무승부 규칙을 적용할 이름의 리스트

draw_rules = ["구사"]
exception_rules = ["38광땡","광떙","장땡","구땡","팔땡","칠땡","육땡","오땡","사땡","삼땡","이땡","일땡"]


# 코인 추가를 할 수 있는 관리자의 사용자명을 정의합니다.
admin_usernames = ['anduin892'
    # 관리자 사용자명을 추가해주세요.
]


# 사용자명과 사용자 ID를 매핑하는 사전
username_user_id_mapping = {}

# 배팅 금액 정보를 저장할 사전
betting_amounts = {}

user_bets = {}

# 전적을 저장할 사용자별 딕셔너리

last_check_in = {}

user_records = {}

# 각 게임의 결과를 저장할 리스트
game_results = []

user_last_check_in_time = {}

user_check_in_count = {}

user_consecutive_check_in_count = {}

ranking_nicknames = {
    1: "고니",
    2: "대길",
    3: "아귀",
    4: "평경장",
    5: "짝귀",
    6: "고광렬",
    7: "정마담",
    8: "곽철용",
    9: "박무석",
    10: "호구"
    # 필요한 만큼 추가...
}


# 전역 변수 초기화
betting_start_time = None
game_started_after_betting = False



async def get_user_coins(user_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT coins FROM users WHERE user_id=?', (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0


async def get_user_coins(user_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT coins FROM users WHERE user_id=?', (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0


async def update_user_coins(user_id, new_amount):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('UPDATE users SET coins=? WHERE user_id=?', (new_amount, user_id))
    conn.commit()


async def get_winnings(user_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT winnings FROM users WHERE user_id=?', (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0


async def get_loses(user_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT loses FROM users WHERE user_id=?', (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0


async def get_draws(user_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT draws FROM users WHERE user_id=?', (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0


async def add_winnings(user_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE Users SET winnings = winnings + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


async def add_loses(user_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE Users SET loses = loses + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


async def add_draws(user_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE Users SET draws = draws + 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()


async def add_coins(user_id, amount):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT coins FROM Users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result:
        coins = result[0]  # 튜플에서 정수 값 추출
        new_coins = coins + amount
        cursor.execute("UPDATE Users SET coins = ? WHERE user_id = ?", (new_coins, user_id))
        conn.commit()
    else:
        pass

    conn.close()


async def sub_coins(user_id, amount):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT coins FROM Users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()

    if result:
        coins = result[0]  # 튜플에서 정수 값 추출
        new_coins = coins - amount
        cursor.execute("UPDATE Users SET coins = ? WHERE user_id = ?", (new_coins, user_id))
        conn.commit()
    else:
        pass

    conn.close()


async def get_ranking():
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()

    query = "SELECT full_name, coins, user_id FROM Users ORDER BY coins DESC LIMIT 10"

    cursor.execute(query)
    ranking = cursor.fetchall()
    conn.close()
    return ranking


async def get_ranking_attendance():
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()

    query = "SELECT full_name, attendance_counts, user_id FROM Users ORDER BY attendance_counts DESC LIMIT 10"

    cursor.execute(query)
    ranking = cursor.fetchall()
    conn.close()
    return ranking


async def update_coins(user_id, amount):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    old_amount = user_coins.get(user_id, 0)  # user_coins[user_id] 대신 user_coins.get(user_id, 0) 사용
    new_amount = old_amount + amount
    if new_amount < 0:
        return False  
    else:
        conn.execute("INSERT OR REPLACE INTO user_coins VALUES (?, ?)", (user_id, new_amount))
        return True


async def manage_coins_command(update: Update, context: Bot, command):
    if update.effective_chat.id not in allowed_group_ids:
        return

    if not update.message.text.startswith(command):
        return

    args = update.message.text.split()[1:]

    if update.effective_user.username not in admin_usernames:
        await bot.send_message(chat_id=update.effective_chat.id, text="관리자만 이 기능을 사용할 수 있습니다.")
        return

    if len(args) not in [1, 2]:
        await bot.send_message(chat_id=update.effective_chat.id, text="명령어 형식이 올바르지 않습니다. '.지급 사용자명 🪙은자액수' 또는 답장에 '.지급 🪙은자액수'로 입력해주세요.")
        return

    if len(args) == 1:  # 답장 형태로 코인을 지급하거나 차감하는 경우
        if update.message.reply_to_message is None:
            await bot.send_message(chat_id=update.effective_chat.id, text="이 명령어는 답장 형태로만 사용할 수 있습니다.")
            return
        user_id = update.message.reply_to_message.from_user.id
        username = update.message.reply_to_message.from_user.username
        amount = int(args[0])
    else:  # 일반적인 경우
        username, amount = args[0], args[1]
        username = username.lstrip('@')  # "@" 기호 제거
        user_id = username_user_id_mapping.get(username)
        if user_id is None:
            await bot.send_message(chat_id=update.effective_chat.id, text=f"사용자명 @{username} 를 찾을 수 없습니다")
            return
        amount = int(amount)

    # 코인 추가 또는 차감 처리
    if command == '.차감':
        amount = -amount  # 차감 명령인 경우에는 amount를 음수로 만들어 update_coins 호출

    success = update_coins(user_id, amount)
    if not success:
        current_coins = user_coins.get(user_id, 0)
        await bot.send_message(chat_id=update.effective_chat.id, text=f"<b>타짜🎴 @{username}</b> 의 현재 🪙은자가 {current_coins:,} 로 부족하여 처리할 수 없습니다.", parse_mode='html')
        return

    if command == '.지급':
        action_text = '추가'
    elif command == '.차감':
        action_text = '차감'

    await bot.send_message(chat_id=update.effective_chat.id, text=f"<b>타짜🎴 @{username}</b> 에게 {abs(amount):,} 🪙은자를 {action_text}하였습니다", parse_mode='html')



async def transfer_coins(from_user_id, to_user_id, amount):
    # 먼저, 기부자가 충분한 코인을 가지고 있는지 확인합니다.
    if await get_user_coins(from_user_id) < amount:
        return False, "기부하려는 🪙은자가 부족합니다.", 0

    # 코인을 기부자로부터 뺍니다.
    await sub_coins(from_user_id, amount)

    # 코인을 수령자에게 추가합니다. 이때, 10%를 차감합니다.
    deducted_amount = int(amount * 0.9)
    await add_coins(to_user_id, deducted_amount)

    return True, "🪙은자가 성공적으로 전송되었습니다.", deducted_amount


async def can_check_attendance(user_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT last_attendance_check FROM Users WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    last_check = result[0] if result else None
    conn.close()

    return last_check is None or datetime.strptime(last_check, "%Y-%m-%d %H:%M:%S").date() != datetime.now().date()


async def perform_attendance_check(user_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT attendance_counts FROM Users WHERE user_id = ?", (user_id,))
    current_attendance_counts = cursor.fetchone()[0]  # 첫 번째 열 값을 가져옵니다.

    new_attendance_counts = current_attendance_counts + 1
    cursor.execute("UPDATE Users SET last_attendance_check = ?, attendance_counts = ? WHERE user_id = ?",
                   (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), new_attendance_counts, user_id))

    conn.commit()
    conn.close()


async def get_attendance_counts(user_id):
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT attendance_counts FROM Users WHERE user_id = ?", (user_id,))
    attendance_counts = cursor.fetchone()
    conn.close()
    return attendance_counts[0] if attendance_counts else None


async def check_in_command(update: Update, context: CallbackContext):
    global allowed_group_ids
    if update.effective_chat.id not in allowed_group_ids:
        return

    if not update.message.text.startswith(".출석체크"):
        return
    user = update.message.from_user
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    first_name = user.first_name
    last_name = user.last_name or ''  # last_name이 없을 수 있으므로 빈 문자열로 처리
    full_name = f"{first_name} {last_name}".strip()

    await add_user(username=username, user_id=user_id, initial_coins=0, full_name=full_name)

    # Get the user's ID
    user_id = update.effective_user.id

    attendance = await get_attendance_counts(user_id)

    if await can_check_attendance(user_id):
        # 추가 보상 지급 여부 확인 및 처리 (10의 배수일 때)
        if attendance % 10 == 0 and attendance != 0:
            await perform_attendance_check(user_id)
            await add_coins(user_id, 300000)  # 300,000
            await bot.send_message(chat_id=update.effective_chat.id,
                                     text=f"<b>타짜🎴 @{username}</b> 🎊축하합니다🎊\n"
                                          f"출석 {attendance}회 달성! 추가로 🪙은자을 받았습니다.", parse_mode='html')
        else:
            await perform_attendance_check(user_id)
            await add_coins(user_id, 30000)    #30,000
            await bot.send_message(chat_id=update.effective_chat.id,
                                      text=f"<b>타짜🎴 @{username}</b>\n"
                                           f"출석 완료! 🪙은자를 받았습니다.", parse_mode='html')

    else:
        await bot.send_message(chat_id=update.effective_chat.id,
                              text=f"<b>타짜🎴 @{username}</b> "
                                   f"오늘은 이미 출석했습니다!\n내일 다시 시도해주세요.",
                              parse_mode='html')


async def check_in_rank_command(update: Update, context: Bot):
        if update.effective_chat.id not in allowed_group_ids:
            return
        if update.message.text.strip() != ".출석랭킹":
            return
        ranking = await get_ranking_attendance()
        ranking_message = "🎴 <b>화산파</b> 출석랭킹 🎴\n"

        message = ''
        message += ranking_message
        for i, (target_full_name, points, user_id) in enumerate(ranking, start=1):
            message += f"\n{i}등 {target_full_name}[{user_id}]\n" \
                       f"{await get_attendance_counts(user_id):,}회\n"

        await bot.send_message(update.effective_chat.id, message, pool_timeout=500, read_timeout=500,
                               write_timeout=500, connect_timeout=500, parse_mode="HTML")
        return


async def transfer_coins_command_handler(update: Update, context: Bot):
    if update.effective_chat.id not in allowed_group_ids:
        return

    if not update.message.text.startswith(".기부"):
        return

    args = update.message.text.split()[1:]

    from_user_id = update.effective_user.id
    from_username = update.effective_user.username

    if len(args) not in [1, 2]:
        await bot.send_message(chat_id=update.effective_chat.id, text="명령어 형식이 올바르지 않습니다. '.기부 @사용자명 🪙은자액수' 또는 답장에 '.기부 🪙은자액수'로 입력해주세요.")
        return

    if len(args) == 1:  # 답장 형태로 코인을 기부하는 경우
        if update.message.reply_to_message is None:
            await bot.send_message(chat_id=update.effective_chat.id, text="이 명령어는 답장 형태로만 사용할 수 있습니다.")
            return
        to_user_id = update.message.reply_to_message.from_user.id
        to_username = update.message.reply_to_message.from_user.username
        amount = int(args[0])
    else:  # 일반적인 경우
        to_username, amount = args[0], args[1]
        to_username = to_username.lstrip('@')  # "@" 기호 제거
        to_user_id = username_user_id_mapping.get(to_username)
        if to_user_id is None:
            await bot.send_message(chat_id=update.effective_chat.id, text=f"사용자명 @{to_username} 를 찾을 수 없습니다")
            return
        amount = int(amount)

    # amount가 0 또는 음수인 경우 처리
    if amount <= 0:
        await bot.send_message(chat_id=update.effective_chat.id, text=f"기부하려는 🪙은자가 없습니다")
        return

    # 인라인 키보드를 만듭니다.
    keyboard = [
        [
            InlineKeyboardButton("예", callback_data=f"YES:{from_user_id}:{to_user_id}:{amount}"),
            InlineKeyboardButton("아니요", callback_data=f"NO:{from_user_id}:{to_user_id}:{amount}")
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    await bot.send_message(chat_id=update.effective_chat.id, text=f"<b>타짜🎴 @{from_username}</b> 님, <b>타짜🎴 @{to_username}</b> 님에게 {amount:,} 🪙은자를 기부하시겠습니까?", reply_markup=reply_markup, parse_mode='html')


async def button(update: Update, context: Bot):
    query = update.callback_query
    await query.answer()  # await 추가

    action, user_id, to_user_id, amount = query.data.split(":")
    user_id = int(user_id)
    to_user_id = int(to_user_id)
    amount = int(amount)

    # 버튼을 누른 사람이 버튼을 만든 사람인지 확인
    if query.from_user.id == user_id:
        from_chat = await bot.get_chat(user_id)  # await 추가
        to_chat = await bot.get_chat(to_user_id)  # await 추가

        from_username = from_chat.username
        to_username = to_chat.username

        if action == "YES":
            success, message, deducted_amount = await transfer_coins(user_id, to_user_id, amount)
            if success:
                await query.edit_message_text(text=f"🪙은자가 성공적으로 전송되었습니다. <b>타짜🎴 @{from_username}</b> 님이 <b>타짜🎴 @{to_username}</b> 님에게 {deducted_amount:,} 🪙은자를 기부하였습니다. (총 {amount:,} 🪙은자 중 10%가 차감되었습니다)", parse_mode='html')
            else:
                await query.edit_message_text(text=message)
        elif action == "NO":
            await query.edit_message_text(text=f"{query.from_user.first_name}, 전송이 취소되었습니다.")

application.add_handler(CallbackQueryHandler(button))


async def callback_query_handler(update: Update, context: Bot):
    query = update.callback_query
    await query.answer()  # 콜백 쿼리에 응답

    data = query.data.split(":")
    action = data[0]
    if action == "transfer":
        from_user_id, to_user_id, amount = map(int, data[1:])
        from_username = await bot.get_chat(from_user_id).username
        to_username = await bot.get_chat(to_user_id).username

        success, message, deducted_amount = await transfer_coins(from_user_id, to_user_id, amount)

        if success:
            await bot.send_message(chat_id=update.effective_chat.id, text=f"<b>타짜🎴 @{from_username}</b> 님이 <b>타짜🎴 @{to_username}</b> 님에게 {deducted_amount:,} 🪙은자을 기부하였습니다. (총 {amount:,} 🪙은자 중 10%가 차감되었습니다)", parse_mode='html')
        else:
            await bot.send_message(chat_id=update.effective_chat.id, text=message)
    elif action == "cancel":
        await bot.send_message(chat_id=update.effective_chat.id, text="코인 기부가 취소되었습니다.")


application.add_handler(CallbackQueryHandler(callback_query_handler))


async def add_record(user_id, result):
    # 사용자의 전적을 업데이트
    records = user_records.get(user_id, [])
    records.append(result)
    # 최대 10개의 전적만 유지
    user_records[user_id] = records[-5:]


async def place_bet_command(update: Update, context: CallbackContext):
    # Get the user's ID
    user_id = update.effective_user.id

    # Get the bet amount from the message text
    args = update.message.text.split()
    if len(args) < 2:
        await bot.send_message(chat_id=update.effective_chat.id, text="배팅 금액을 입력해주세요.")
        return

    try:
        amount = int(args[1])  # Assuming that the bet amount is the second word in the message
    except ValueError:
        await bot.send_message(chat_id=update.effective_chat.id, text="올바른 배팅 금액을 입력해주세요.")
        return

    # Fetch latest coin info from database.
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT coins FROM users WHERE user_id=?', (user_id,))
    row = cursor.fetchone()

    if row is None:
         # If there's no information about this user in database yet,
        # Initialize it.
        cursor.execute('INSERT INTO users (user_id, coins) VALUES (?, ?)', (user_id, 0))
        conn.commit()
        user_coins = 0
    else:
        user_coins = row[0]


    print(f"Amount: {amount}, User coins: {user_coins}")
     
    if amount > user_coins:
        await bot.send_message(chat_id=update.effective_chat.id, text="보유한 코인보다 많은 금액을 배팅할 수 없습니다.")
        return
    
# ... rest of your code ..
    global game_in_progress, betting_start_time

    if update.effective_chat.id not in allowed_group_ids:
        return

    if game_in_progress:
        await bot.send_message(chat_id=update.effective_chat.id, text="게임이 진행중이므로 베팅할 수 없습니다.")
        return

    global betting_start_time  # 배팅 시작 시간을 전역 변수로 선언

    args = update.message.text.split()  # 첫 번째 단어는 팀명이므로 그대로 사용합니다.              
    if args is None or len(args) != 2:
        await bot.send_message(chat_id=update.effective_chat.id, text="명령어 형식이 올바르지 않습니다. '.팀명 🪙은자액수'로 입력해주세요")
        return
    
    team, amount = args
    amount = int(amount)

    # 배팅 금액이 0 혹은 음수인 경우 거부
    if amount <= 0:
        await bot.send_message(chat_id=update.effective_chat.id, text="배팅가능한 🪙은자가 부족합니다")
        return

    # 팀명을 전체 이름으로 변환
    if team == ".한국":
        team = "한국팀"
    elif team == ".일본":
        team = "일본팀"
    elif team == ".무":
        team = "무승부"

    if team not in ["한국팀", "일본팀", "무승부"]:
        await bot.send_message(chat_id=update.effective_chat.id, text="올바른 팀명을 입력해주세요 (.한국 .일본 .무)")
        return

    # 사용자명으로부터 사용자 ID를 검색
    user_id = update.effective_user.id
    cursor.execute('SELECT coins FROM users WHERE user_id=?', (user_id,))

    # 사용자가 이미 베팅한 경우 에러 메시지 전송
    if user_id in betting_amounts:
        await bot.send_message(chat_id=update.effective_chat.id, text="이미 베팅한 타짜입니다")
        return

    if amount > user_coins:
        await bot.send_message(chat_id=update.effective_chat.id,
                         text=f"현재 보유하신 🪙은자: {user_coins}\n"
                              f"배팅 가능한 최대 🪙은자: {user_coins}\n"
                              f"배팅금액이 초과되었습니다.")
        return

# 배팅 금액 저장
    betting_amounts[user_id] = amount
    user_bets[user_id] = team

# Update the user's coins in the database.
    new_user_coin = user_coins - amount
    cursor.execute('UPDATE users SET coins=? WHERE user_id=?', (new_user_coin, user_id))
    conn.commit()


# The rest of your code...
    # 배팅 시작 시간 기록
    if betting_start_time is None:
        betting_start_time = time.time()

    # 배팅 시작 후 남은 시간 계산
    if betting_start_time is not None:
        remaining_time = 60 - (time.time() - betting_start_time)
        if remaining_time < 0:
            remaining_time = 0
        await bot.send_message(chat_id=update.effective_chat.id, text=f"{amount:,} 🪙은자를 *{team}*에 배팅하였습니다.\n게임 시작까지 남은 시간: *{remaining_time:.0f}*초", parse_mode='Markdown')
    else:
        await bot.send_message(chat_id=update.effective_chat.id,text=f"{amount:,} 🪙은자를 *{team}*에 배팅하였습니다.", parse_mode='Markdown')

    
async def send_stickers_game_periodic():
    global betting_start_time  # 배팅 시작 시간을 전역 변수로 선언

    while True:
        # 이 부분은 기존의 배팅이 없을 경우를 처리하는 코드입니다.
        if len(betting_amounts) == 0:
            await asyncio.sleep(5)
            continue

        # 배팅 시작 후 일정 시간이 지나지 않았으면 게임을 시작하지 않음
        if betting_start_time and time.time() - betting_start_time < 60:  # 60초 동안 대기
            await asyncio.sleep(5)
            continue

        for chat_id in allowed_group_ids:
            await send_stickers_game(chat_id)

        # 게임이 끝난 후 배팅 시작 시간을 초기화
        betting_start_time = None

        # 1분 대기
        await asyncio.sleep(60)


async def send_stickers_game(chat_id):
    global game_in_progress  # 전역 변수를 사용하려면 이를 함수 내에서 선언해야 합니다.

    if chat_id not in allowed_group_ids:
        return
    game_in_progress = True

    korea_team_stickers = []
    japan_team_stickers = []
    sticker_messages = []

    # 스티커 아이디 리스트를 섞음
    random.shuffle(stickers)

    for i in range(4):
        # 카드를 받을 팀 결정
        team = "🇰🇷*한국팀*" if i % 2 == 0 else "🇯🇵*일본팀*"
        # 카드의 종류 결정
        card = "첫 번째" if i // 2 == 0 else "두 번째"
        # 카드 정보 저장
        sticker = stickers[i]
        message = f"{team}이 {card} 카드를 받았습니다."

        # 스티커와 메시지를 리스트에 추가
        sticker_messages.append((sticker, message))

        if team == "🇰🇷*한국팀*":
            korea_team_stickers.append(sticker)
        else:
            japan_team_stickers.append(sticker)

    for sm in sticker_messages:
        await bot.send_sticker(chat_id=chat_id, sticker=sm[0])
        await bot.send_message(chat_id=chat_id, text=sm[1], parse_mode='Markdown')
        await asyncio.sleep(2)

    # 스티커 조합의 점수에 따라 팀의 점수를 계산
    korea_score_info = sorted_scores.get(tuple(sorted(korea_team_stickers)), {"score": 0, "name": "없음"})
    japan_score_info = sorted_scores.get(tuple(sorted(japan_team_stickers)), {"score": 0, "name": "없음"})

    korea_score = korea_score_info["score"]
    japan_score = japan_score_info["score"]

    for rule in special_rules:
        if (korea_score_info["name"], japan_score_info["name"]) == rule:
            japan_score = 0  #
        elif (japan_score_info["name"], korea_score_info["name"]) == rule:
            korea_score = 0  #

    # 특별한 무승부 규칙 적용
    for rule in draw_rules:
        if korea_score_info["name"] == rule and japan_score_info["name"] not in exception_rules:
            japan_score = korea_score  #
        elif japan_score_info["name"] == rule and korea_score_info["name"] not in exception_rules:
            korea_score = japan_score  #

    winning_team = None
    if korea_score > japan_score:
        game_results.append("🇰🇷")
        await bot.send_message(chat_id=chat_id, text=f"🇰🇷*한국팀*이 *{korea_score_info['name']}*으로 승리하였습니다.",
                         parse_mode='Markdown')
        await show_game_records(chat_id)
        # 배팅 금액에 따라 코인 지급
        for user_id, amount in betting_amounts.items():
            if user_bets[user_id] == "한국팀":
                # 해당 사용자가 한국팀에 배팅했을 경우 처리
                winnings = round(amount * 1.95)
                await add_coins(user_id, winnings)
                await add_record(user_id, "승")  # 전적 업데이트: 승리
                await add_winnings(user_id)
                await bot.send_message(chat_id=chat_id, text=f"<b>타짜🎴</b>에게 {winnings:,} 🪙은자을 지급하였습니다", parse_mode='html')
            else:  # 해당 사용자가 일본팀에 배팅했을 경우
                await add_record(user_id, "패")  # 전적 업데이트: 패배
                await add_loses(user_id)
                await bot.send_message(chat_id=chat_id, text=f"<b>타짜🎴</b>가 {amount:,} 🪙은자을 잃었습니다", parse_mode='html')
    elif korea_score < japan_score:
        game_results.append("🇯🇵")
        await bot.send_message(chat_id=chat_id, text=f"🇯🇵*일본팀*이 *{japan_score_info['name']}*으로 승리하였습니다",
                         parse_mode='Markdown')
        await show_game_records(chat_id)
        # 배팅 금액을 잃음
        for user_id, amount in betting_amounts.items():
            if user_bets[user_id] == "일본팀":  # 해당 사용자가 일본팀에 배팅했을 경우
                winnings = round(amount * 1.95)
                await add_coins(user_id, winnings)
                await add_record(user_id, "승")  # 전적 업데이트: 승리
                await add_winnings(user_id)
                await bot.send_message(chat_id=chat_id, text=f"<b>타짜🎴</b>에게 {winnings:,} 🪙은자을 지급하였습니다", parse_mode='html')
            else:  # 해당 사용자가 한국팀에 배팅했을 경우
                await add_record(user_id, "패")  # 전적 업데이트: 패배
                await add_loses(user_id)
                await bot.send_message(chat_id=chat_id, text=f"<b>타짜🎴</b>가 {amount:,} 🪙은자을 잃었습니다", parse_mode='html')

    else:
        game_results.append("🏳️")
        await bot.send_message(chat_id=chat_id, text="*비겼습니다*", parse_mode='Markdown')
        await show_game_records(chat_id)
        # 배팅 금액을 반환
        for user_id, amount in betting_amounts.items():
            if user_bets[user_id] == "무승부":  # 해당 사용자가 무승부에 배팅했을 경우
                winnings = round(amount * 5)
                await add_coins(user_id, winnings)
                await add_record(user_id, "승")  # 전적 업데이트: 승리
                await add_winnings(user_id)
                await bot.send_message(chat_id=chat_id, text=f"<b>타짜🎴</b>에게 {winnings:,} 🪙은자을 지급하였습니다", parse_mode='html')
            else:  # 해당 사용자가 팀에 배팅했을 경우
                await add_record(user_id, "패")  # 전적 업데이트: 패배
                await add_draws(user_id)
                await add_coins(user_id, amount)  # 배팅한 코인 반환
                await bot.send_message(chat_id=chat_id, text=f"<b>타짜🎴</b>가 배팅한 {amount:,} 🪙은자을 반환하였습니다", parse_mode='html')
                ...

            # for user_id in betting_amounts.keys():
            #     conn = sqlite3.connect('my_database.db')
            #     cursor = conn.cursor()
            #     result = '승' if user_bets[user_id] == winning_team else '패'
            #     cursor.execute('UPDATE bets SET result=? WHERE user_id=? AND bet_on=?',
            #                    (result, user_id, user_bets[user_id]))
            #     conn.commit()

                # user_bets[user_id] = team  # 기존 코드
    user_bets[user_id] = team
    # cursor.execute('INSERT INTO bets (user_id, bet_amount, bet_on) VALUES (?, ?, ?)',
    #                (user_id, amount, team))
    # conn.commit()

    game_in_progress = False

    # 배팅 금액 초기화
    betting_amounts.clear()
    user_bets.clear()


async def show_ranking_command(update: Update, context: Bot):
    if update.effective_chat.id not in allowed_group_ids:
        return
    if update.message.text.strip() != ".랭킹":
        return
    ranking = await get_ranking()
    ranking_message = "🎴 <b>화산파</b> 섯다랭킹 🎴\n"

    message = ''
    message += ranking_message
    for i, (target_full_name, points, user_id) in enumerate(ranking, start=1):
        message += f"\n{i}등 {target_full_name}[{user_id}]\n" \
                   f"{points:,} 은자\n"

    await bot.send_message(update.effective_chat.id, message, pool_timeout=500, read_timeout=500,
                           write_timeout=500, connect_timeout=500, parse_mode="HTML")
    return


async def calculate_consecutive_wins(records):
    consecutive_wins = 0
    for record in reversed(records):
        if record == '승':
            consecutive_wins += 1
        else:
            break

    return consecutive_wins


async def show_records_command(update: Update, context: Bot):
    if update.effective_chat.id not in allowed_group_ids:
        return
    user_id = update.effective_user.id
    records = user_records.get(user_id, [])

    if not records:
        await bot.send_message(chat_id=update.effective_chat.id, text="전적이 없습니다",)
        return

    message = "*최근 전적*:\n"
    for index, record in enumerate(records, start=1):
        message += f"{index}. {record}\n"

    await bot.send_message(chat_id=update.effective_chat.id, text=message,)


async def show_my_info_command(update: Update, context: CallbackContext):
    if update.effective_chat.id not in allowed_group_ids:
        return
    if update.message.text.strip() != ".나":
        return

    user_id = update.effective_user.id
    username = update.message.from_user.username

    # Fetch latest coin info from database.
    conn = sqlite3.connect('my_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT coins FROM users WHERE user_id=?', (user_id,))
    row = cursor.fetchone()
    coins = row[0] if row else 0

    # 최근 전적 출력
    records = user_records.get(user_id, [])

    winnings = await get_winnings(user_id)
    losses = await get_loses(user_id)
    draws = await get_draws(user_id)

    consecutive_wins = await calculate_consecutive_wins(records)

    records_info = f"<b>전체 전적:</b> {winnings}승 {draws}무 {losses}패\n<b>연승 현황:</b> {consecutive_wins}연승"
    
    extra_hyperlink = 'https://t.me/KGLalliance/6'
    extra_link_text = 'W벳'
  

    # 하이퍼링크 생성
    hyperlink = 'https://t.me/Cho_myg'

    keyboard = [[InlineKeyboardButton('제휴문의', url=hyperlink)]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # 사용자명과 사용자 ID, 보유 코인, 최근 전적을 출력
    info_message = f"""
<b>타짜🎴:@{username}</b>
<b>타짜🆔: {user_id}</b>
<b>은자🪙: {coins:,}</b>
    
{records_info}
    
🇰🇷<b>화산파 보증 도박장</b>🇯🇵

<a href="{extra_hyperlink}">{extra_link_text}</a> - 1+1 2+2 3+3 ~200+60 외 30%
    """
    await bot.send_message(chat_id=update.effective_chat.id, text=info_message, parse_mode='html', disable_web_page_preview=True, reply_markup=reply_markup)


async def show_game_records(chat_id):
    # 게임 결과가 없는 경우 사용자에게 알림
    if not game_results:
        game_records_str = "아직 게임 결과가 없습니다."
    else:
        # 초기 게임 번호 설정
        game_number = 1
        game_records_str = f"{game_number} {game_results[0]}"
        last_winning_team = game_results[0]
        for i in range(1, len(game_results)):
            # 이전 결과와 현재 결과를 비교하여 같거나 무승부일 경우 연속으로 출력, 다르면 새 줄로 출력
            if game_results[i] == last_winning_team or game_results[i] == "🏳️":
                game_records_str += game_results[i]
            else:
                game_records_str += ")"
                game_number += 1
                game_records_str += "\n" + f"{game_number} {game_results[i]}"
                last_winning_team = game_results[i]

        # 게임 결과가 50개 이상이면 초기화
        if len(game_results) >= 50:
            game_results.clear()

    # 현재 게임 회차 및 총 회차 표시 추가
    game_records_str += f"\n현재 {len(game_results)} / 50 회차 진행중"

    await bot.send_message(chat_id=chat_id, text=game_records_str)


async def random_coin_award_handler(update: Update, context: Bot):
    if update.effective_chat.id not in allowed_group_ids:
        return

    user_id = update.effective_user.id
    username = update.effective_user.username

    # 1% 확률로 코인을 지급합니다.
    if random.random() < 0.01:
        amount = random.randint(1000, 10000)  # 1000에서 10000 사이의 랜덤한 값으로 코인 지급
        add_coins(user_id, amount)
        await bot.send_message(chat_id=update.effective_chat.id, text=f"<b>타짜🎴 @{username}</b> {amount:,} 🪙은자획득!", parse_mode='html')


async def show_commands_command(update: Update, context: Bot):
    if update.effective_chat.id not in allowed_group_ids:
        return

    if update.message.text.strip() != ".명령어":
        return

    commands_message = "<b>🎴화산파 섯다 명령어 🎴            </b>\n\n"
    commands_message += "<b>.기부</b>\n"
    commands_message += "<b>.출석체크</b>\n"
    commands_message += "<b>.출석랭킹</b>\n"
    commands_message += "<b>.랭킹</b>\n"
    commands_message += "<b>.한국 .일본 .무</b>\n"
    commands_message += "<b>.설명</b>\n"
    commands_message += "<b>.나</b>"
    # 필요한 만큼 추가...

    await bot.send_message(chat_id=update.effective_chat.id, text=commands_message, parse_mode='html')


async def game_description_command(update: Update, context: Bot):
    if update.effective_chat.id not in allowed_group_ids:
        return
    if not update.message.text.startswith(".설명"):
        return

    game_description = """
    <b>섯다🎴게임 설명 🎮:</b>

    배팅은 한국 무 일본 이렇게 가능 무배당은 5배
    출석체크 3만🪙은자지급, 10회 달성마다 30만🪙은자지급
    기부기능 수수료 10% 차감(플레이타임 늘리기위해 수수료발생)
    족보는 멍텅구리 구사 제외 전부다있음
    채팅시 일정확률로 1000~10000 🪙은자 지급
    """.strip()

    await bot.send_message(chat_id=update.effective_chat.id, text=game_description, parse_mode='html')

description_handler = MessageHandler(filters.TEXT & filters.Regex('^\.설명$'), game_description_command)
application.add_handler(description_handler)


description_handler = MessageHandler(filters.TEXT & filters.Regex('^\.설명$'), game_description_command)
application.add_handler(description_handler)

dot_show_commands_handler = MessageHandler(filters.TEXT & filters.Regex('^\.명령어$'), show_commands_command)
application.add_handler(dot_show_commands_handler)


# 코인 추가 커맨드 핸들러 등록
dot_add_coins_handler = MessageHandler(filters.TEXT & filters.Regex('^\.지급'), lambda update, context: manage_coins_command(update, context, '.지급'))
application.add_handler(dot_add_coins_handler)

dot_subtract_coins_handler = MessageHandler(filters.TEXT & filters.Regex('^\.차감'), lambda update, context: manage_coins_command(update, context, '.차감'))
application.add_handler(dot_subtract_coins_handler)


dot_place_bet_handler = MessageHandler(filters.TEXT & (filters.Regex('^\.한국') | filters.Regex('^\.일본') | filters.Regex('^\.무')), place_bet_command)
application.add_handler(dot_place_bet_handler)


dot_ranking_handler = MessageHandler(filters.TEXT & filters.Regex('^\.랭킹$'), show_ranking_command)
application.add_handler(dot_ranking_handler)

dot_transfer_handler = MessageHandler(filters.TEXT & filters.Regex('^\.기부'), transfer_coins_command_handler)
application.add_handler(dot_transfer_handler)


dot_show_my_info_handler = MessageHandler(filters.TEXT & filters.Regex('^\.나$'), show_my_info_command)
application.add_handler(dot_show_my_info_handler)

check_in_handler = MessageHandler(filters.TEXT & filters.Regex('^\.출석체크$'), check_in_command)
check_in_rank_handler = MessageHandler(filters.TEXT & filters.Regex('^\.출석랭킹$'), check_in_rank_command)

application.add_handler(check_in_handler)
application.add_handler(check_in_rank_handler)


random_coin_handler = MessageHandler(filters.TEXT, random_coin_award_handler)
application.add_handler(random_coin_handler)


# 모든 메시지를 처리하는 함수
async def handle_all_messages(update: Update, context: Bot):
    text = update.message.text
    user = update.message.from_user
    user_id = update.message.from_user.id
    username = update.message.from_user.username
    first_name = user.first_name
    last_name = user.last_name or ''  # last_name이 없을 수 있으므로 빈 문자열로 처리
    full_name = f"{first_name} {last_name}".strip()

    message_id = update.message.message_id
    replying_message = update.message.reply_to_message
    user = update.effective_user
    add_user(username=username, user_id=user_id, initial_coins=0, full_name=full_name)

    print(f"사용자명: {user.username}, 사용자 ID: {user.id}")


# 모든 메시지를 처리하는 핸들러 등록
async def run():
    # add handlers
    all_messages_handler = MessageHandler(filters.TEXT, handle_all_messages)
    application.add_handler(all_messages_handler)

    done_event = asyncio.Event()
    # Run application and play_65_games() within the same event loop
    async with application:
        await application.initialize()  # inits bot, update, persistence
        await application.start()
        await application.updater.start_polling()
        # 게임 시작 태스크 생성
        asyncio.create_task(send_stickers_game_periodic())
        # 게임 루프와 메시지 핸들러를 동시에 실행
        await done_event.wait()
        await application.stop()

if __name__ == "__main__":
    asyncio.run(run())
import asyncio
import json
import time
from datetime import datetime, timedelta
import schedule
from instagrapi import Client

cl = Client()

try:
    cl.login('your_username', 'your_password')
except Exception as e:
    print(f"Error during login: {e}")

FOLLOW_LOG_FILE = 'follow_log.json'

def load_follow_log():
    try:
        with open(FOLLOW_LOG_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_follow_log(log):
    with open(FOLLOW_LOG_FILE, 'w') as file:
        json.dump(log, file)

async def follow_user(user):
    try:
        await cl.user_follow(user.pk)
        follow_log = load_follow_log()
        follow_log[user.username] = {'followed_at': datetime.now().isoformat(), 'followed_back': False}
        save_follow_log(follow_log)
        print(f"Followed {user.username}")
    except Exception as e:
        print(f"Error following {user.username}: {e}")

async def follow_users():
    try:
        suggestions = cl.account_suggestions()
        follow_log = load_follow_log()
        followed_count = 0

        for user in suggestions:
            if followed_count >= 5:
                break
            if user.username not in follow_log:
                await follow_user(user)
                followed_count += 1
                await asyncio.sleep(720)  # 12 minutes in seconds

        print(f"Followed {followed_count} new users in this hour")
    except Exception as e:
        print(f"Error in follow_users: {e}")

def check_unfollow_users():
    try:
        follow_log = load_follow_log()
        now = datetime.now()
        updated_log = {}

        for username, info in follow_log.items():
            followed_at = datetime.fromisoformat(info['followed_at'])
            if (now - followed_at) >= timedelta(days=7):
                user_id = cl.user_id_from_username(username)
                if not cl.user_following(user_id):
                    cl.user_unfollow(user_id)
                    print(f"Unfollowed {username} for not following back")
                else:
                    info['followed_back'] = True
                    updated_log[username] = info
            else:
                updated_log[username] = info

        save_follow_log(updated_log)
    except Exception as e:
        print(f"Error in check_unfollow_users: {e}")

async def follow_scheduler():
    while True:
        await follow_users()
        await asyncio.sleep(3600 - 5 * 720)  # Adjust sleep time to fit within the hour

def start_scheduler():
    schedule.every().day.at("00:00").do(check_unfollow_users)

    loop = asyncio.get_event_loop()
    loop.create_task(follow_scheduler())

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    try:
        start_scheduler()
    except Exception as e:
        print(f"Error in main: {e}")

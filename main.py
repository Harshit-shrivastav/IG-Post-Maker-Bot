import logging
import os
import time
import asyncio
import json
import threading
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai
from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired
import asyncpraw
import aiohttp
import schedule
import pickle

logging.basicConfig(level=logging.INFO)

GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')
REDDIT_CLIENT_ID = os.getenv('REDDIT_CLIENT_ID')
REDDIT_CLIENT_SECRET = os.getenv('REDDIT_CLIENT_SECRET')
REDDIT_USER_AGENT = os.getenv('REDDIT_USER_AGENT')

if not all([GOOGLE_API_KEY, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT]):
    raise EnvironmentError("Please set all required environment variables.")

prompt = "You are a very talented Instagram post captions generator, generate post caption for this image and also include hashtags."
font_path = 'assets/font.ttf'
logo_path = 'assets/instagram_logo.png'
posted_images_file = 'posted_images.json'
FOLLOW_LOG_FILE = 'follow_log.json'
SESSION_FILE = 'instagram_session.pkl'

reddit = asyncpraw.Reddit(
    client_id=REDDIT_CLIENT_ID,
    client_secret=REDDIT_CLIENT_SECRET,
    user_agent=REDDIT_USER_AGENT
)

def load_posted_images():
    if os.path.exists(posted_images_file):
        with open(posted_images_file, 'r') as f:
            return json.load(f)
    return []

def save_posted_images(posted_images):
    with open(posted_images_file, 'w') as f:
        json.dump(posted_images, f)

def load_follow_log():
    try:
        with open(FOLLOW_LOG_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_follow_log(log):
    with open(FOLLOW_LOG_FILE, 'w') as file:
        json.dump(log, file)

def get_session():
    try:
        with open(SESSION_FILE, 'rb') as f:
            session = pickle.load(f)
            return session
    except FileNotFoundError:
        return None

def save_session(session):
    with open(SESSION_FILE, 'wb') as f:
        pickle.dump(session, f)

def login_instagram():
    session = get_session()
    if session is None:
        client = Client()
        try:
            client.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
            save_session(client)
        except ChallengeRequired as e:
            print(f"Challenge required: {e}")
            handle_challenge(client)
        return client
    else:
        return session

def handle_challenge(client):
    challenge_url = client.last_json.get('challenge', {}).get('url')
    if challenge_url:
        choice = input("Enter 1 to verify via email or 0 to verify via phone: ")
        client.challenge_resolve(challenge_url, choice)
        code = input("Enter the code sent to your device: ")
        client.challenge_code(challenge_url, code)
        save_session(client)
    else:
        raise Exception("Challenge URL not found")

client = login_instagram()

async def get_image_caption(prompt, image):
    try:
        llm = genai.GenerativeModel('gemini-pro-vision')
        response = await llm.generate_content([prompt, image])
        return response.text
    except Exception as e:
        logging.error(f"Error generating response with image: {e}")
        return "Error generating caption."

async def resize_image_for_instagram(image_path, output_path, size=(1080, 1080)):
    try:
        logging.info("Resizing image for Instagram.")
        image = Image.open(image_path)
        image.thumbnail(size, Image.Resampling.LANCZOS)
        background = Image.new('RGB', size, (255, 255, 255))
        offset = ((size[0] - image.size[0]) // 2, (size[1] - image.size[1]) // 2)
        background.paste(image, offset)
        background.save(output_path)
        logging.info("Image resized successfully.")
        return output_path
    except Exception as e:
        logging.error(f"Error resizing image: {e}")
        raise

async def add_transparent_watermark(image_path, watermark_text, logo_path, output_path, font_path=None, font_size=50, opacity=200):
    try:
        logging.info("Adding watermark to the image.")
        image = Image.open(image_path).convert("RGBA")
        watermark_layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
        watermark_draw = ImageDraw.Draw(watermark_layer)
        
        try:
            if font_path:
                font = ImageFont.truetype(font_path, font_size)
            else:
                font = ImageFont.load_default()
        except Exception as e:
            logging.error(f"Error loading font: {e}, falling back to default font.")
            font = ImageFont.load_default()
        
        logo = Image.open(logo_path).convert("RGBA")
        logo.thumbnail((font_size, font_size), Image.Resampling.LANCZOS)

        text_bbox = watermark_draw.textbbox((0, 0), watermark_text, font=font)
        text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]

        logo_width, logo_height = logo.size
        total_width = logo_width + text_width + 10
        total_height = max(logo_height, text_height)
        x_position = image.size[0] - total_width - 30
        y_position = image.size[1] - total_height - 30
        text_position = (x_position + logo_width + 10, y_position + (total_height - text_height) // 2)
        logo_position = (x_position, y_position + (total_height - logo_height) // 2)

        rect_margin = 10
        background_rect = [
            x_position - rect_margin, 
            y_position - rect_margin, 
            x_position + total_width + rect_margin, 
            y_position + total_height + rect_margin * 2
        ]
        watermark_draw.rectangle(background_rect, fill=(0, 0, 0, 128))

        shadow_offset = 2
        shadow_color = (0, 0, 0, int(opacity * 0.8))
        watermark_draw.text((text_position[0] + shadow_offset, text_position[1] + shadow_offset), watermark_text, font=font, fill=shadow_color)

        watermark_draw.text(text_position, watermark_text, (255, 255, 255, opacity), font=font)
        
        watermark_layer.paste(logo, logo_position, logo)

        watermarked_image = Image.alpha_composite(image, watermark_layer)
        watermarked_image = watermarked_image.convert("RGB")
        watermarked_image.save(output_path)
        logging.info("Watermark added successfully.")
        return output_path
    except Exception as e:
        logging.error(f"Error adding watermark: {e}")
        raise

async def upload_to_instagram(image_path, caption):
    try:
        await client.photo_upload(image_path, caption)
        logging.info("Image uploaded to Instagram successfully.")
    except Exception as e:
        logging.error(f"Error uploading image to Instagram: {e}")
        raise
        
async def fetch_latest_image(subreddit_name):
    subreddit = await reddit.subreddit(subreddit_name)
    async for submission in subreddit.new(limit=10):
        if submission.url.endswith(('.jpg', '.jpeg', '.png')):
            return submission.url
    return None

async def download_image(url, output_path):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    with open(output_path, 'wb') as f:
                        f.write(await response.read())
                    logging.info(f'Downloaded {url} to {output_path}')
                    return output_path
    except aiohttp.ClientError as e:
        logging.error(f"Error downloading image: {e}")
    return None

async def process_reddit_image():
    communities = ["pics", "earthporn", "aww"]
    posted_images = load_posted_images()

    for community in communities:
        logging.info(f"Fetching image from r/{community}...")
        try:
            image_url = await fetch_image_from_reddit(community)
            if image_url and image_url not in posted_images:
                logging.info(f"New image found: {image_url}")
                image_path = await download_image(image_url, "downloaded_image.jpg")
                if image_path:
                    resized_image_path = await resize_image_for_instagram(image_path, "resized_image.jpg")
                    watermarked_image_path = await add_transparent_watermark(resized_image_path, "MyWatermark", logo_path, "watermarked_image.jpg", font_path)
                    try:
                        caption = await get_image_caption(prompt, watermarked_image_path)
                        await upload_to_instagram(watermarked_image_path, caption)
                        posted_images.append(image_url)
                        save_posted_images(posted_images)
                    except Exception as e:
                        logging.error(f"Error processing and uploading image: {e}")
                else:
                    logging.error(f"Failed to download image from {image_url}")
            else:
                logging.info(f"No new images found in r/{community}")
        except Exception as e:
            logging.error(f"Error fetching image from r/{community}: {e}")

def check_unfollow_users():
    try:
        follow_log = load_follow_log()
        now = datetime.now()
        updated_log = {}

        for username, info in follow_log.items():
            followed_at = datetime.fromisoformat(info['followed_at'])
            if (now - followed_at) >= timedelta(days=7):
                user_id = client.user_id_from_username(username)
                if not client.user_following(user_id):
                    client.user_unfollow(user_id)
                    logging.info(f"Unfollowed {username} for not following back")
                else:
                    info['followed_back'] = True
                    updated_log[username] = info
            else:
                updated_log[username] = info

        save_follow_log(updated_log)
    except Exception as e:
        logging.error(f"Error in check_unfollow_users: {e}")

async def follow_user(user):
    try:
        client.user_follow(user.pk)
        follow_log = load_follow_log()
        follow_log[user.username] = {'followed_at': datetime.now().isoformat(), 'followed_back': False}
        save_follow_log(follow_log)
        logging.info(f"Followed user: {user.username}")
    except Exception as e:
        logging.error(f"Error following user {user.username}: {e}")

async def follow_users():
    try:
        suggestions = await client.user_suggested()
        followed_count = 0
        follow_log = load_follow_log()

        for user in suggestions:
            if followed_count >= 5:
                break
            if user.username not in follow_log:
                await follow_user(user)
                followed_count += 1
                await asyncio.sleep(720)  # 12 minutes in seconds

        logging.info(f"Followed {followed_count} new users in this hour")
    except Exception as e:
        logging.error(f"Error in follow_users: {e}")

async def follow_scheduler():
    while True:
        await follow_users()
        await asyncio.sleep(3600 - 5 * 720)  # Adjust sleep time to fit within the hour

async def run_periodically():
    while True:
        await process_reddit_image()
        await asyncio.sleep(14400)  # Every 4 hours

def start_async_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_periodically())

def start_scheduler():
    schedule.every().day.at("00:00").do(check_unfollow_users)

    loop = asyncio.get_event_loop()
    loop.create_task(follow_scheduler())

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == "__main__":
    try:
        loop = asyncio.new_event_loop()
        thread = threading.Thread(target=start_async_loop, args=(loop,), name="RedditImageScheduler", daemon=True)
        thread.start()
        start_scheduler()
    except Exception as e:
        logging.error(f"Error in main: {e}")

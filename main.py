import logging
import os
import time
import asyncio
import json
import threading
from telethon import TelegramClient, events
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai
from instagrapi import Client
import asyncpraw
import aiohttp

logging.basicConfig(level=logging.INFO)

# Ensure the environment variables are set
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('BOT_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')
reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
reddit_user_agent = os.getenv('REDDIT_USER_AGENT')

if not all([api_id, api_hash, bot_token, GOOGLE_API_KEY, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD, reddit_client_id, reddit_client_secret, reddit_user_agent]):
    raise EnvironmentError("Please set all required environment variables.")

prompt = "You are a very talented Instagram post captions generator, generate post caption for this image and also include hashtags."
client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)
font_path = 'assets/font.ttf'
logo_path = 'assets/instagram_logo.png'
posted_images_file = 'posted_images.json'

reddit = asyncpraw.Reddit(
    client_id=reddit_client_id,
    client_secret=reddit_client_secret,
    user_agent=reddit_user_agent
)

def load_posted_images():
    if os.path.exists(posted_images_file):
        with open(posted_images_file, 'r') as f:
            return json.load(f)
    return []

def save_posted_images(posted_images):
    with open(posted_images_file, 'w') as f:
        json.dump(posted_images, f)

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

def check_instagram_login():
    try:
        cl = Client()
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        profile = cl.account_info()
        logging.info(f"Instagram login successful. Logged in as: {profile.full_name}")
    except Exception as e:
        logging.error(f"Error logging in to Instagram: {e}")
        raise

async def upload_to_instagram(image_path, caption):
    try:
        logging.info("Uploading image to Instagram.")
        cl = Client()
        cl.login(INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD)
        cl.photo_upload(image_path, caption)
        logging.info("Image uploaded to Instagram successfully.")
    except Exception as e:
        logging.error(f"Error uploading to Instagram: {e}")
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
    communities = ['pics', 'earthporn', 'aww']
    posted_images = load_posted_images()
    
    for community in communities:
        logging.info(f'Fetching image from r/{community}...')
        try:
            image_url = await fetch_latest_image(community)
            if image_url and image_url not in posted_images:
                image_path = 'downloaded_image.jpg'
                image_path = await download_image(image_url, image_path)
                if image_path:
                    try:
                        resized_image_path = 'resized_image.jpg'
                        await resize_image_for_instagram(image_path, resized_image_path)
                        watermarked_image_path = 'watermarked_image.jpg'
                        watermark_text = '@ConfessionsOfADev'
                        await add_transparent_watermark(resized_image_path, watermark_text, logo_path, watermarked_image_path, font_path=font_path)
                        image_pil = Image.open(watermarked_image_path)
                        caption = await get_image_caption(prompt, image_pil)
                        await upload_to_instagram(watermarked_image_path, caption)
                        posted_images.append(image_url)
                        save_posted_images(posted_images)
                        break
                    except Exception as e:
                        logging.error(f"Error processing image {image_path}: {e}")
                    finally:
                        try:
                            os.remove(image_path)
                            os.remove(resized_image_path)
                            os.remove(watermarked_image_path)
                        except Exception as e:
                            logging.error(f"Error cleaning up files: {e}")
        except Exception as e:
            logging.error(f"Error fetching image from r/{community}: {e}")

def run_periodically():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        while True:
            loop.run_until_complete(process_reddit_image())
            time.sleep(14400)  # Sleep for 4 hours
    finally:
        loop.close()

print("Checking out Instagram.")
check_instagram_login()
print("Bot Successfully started.")

# Schedule the Reddit image processing
threading.Thread(target=run_periodically, name="RedditImageScheduler", daemon=True).start()

client.run_until_disconnected()

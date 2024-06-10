import logging
import os
import time
import asyncio
from telethon import TelegramClient, events
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai
from instagrapi import Client
import praw
import requests

logging.basicConfig(level=logging.INFO)

# Ensure the environment variables are set
api_id = os.getenv('API_ID')
api_hash = os.getenv('API_HASH')
bot_token = os.getenv('BOT_TOKEN')
GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
INSTAGRAM_USERNAME = os.getenv('INSTAGRAM_USERNAME')
INSTAGRAM_PASSWORD = os.getenv('INSTAGRAM_PASSWORD')

if not all([api_id, api_hash, bot_token, GOOGLE_API_KEY, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD]):
    raise EnvironmentError("Please set all required environment variables: API_ID, API_HASH, BOT_TOKEN, GOOGLE_API_KEY, INSTAGRAM_USERNAME, INSTAGRAM_PASSWORD.")

prompt = "You are a very talented Instagram post captions generator, generate post caption for this image and also include hashtags."

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

font_path = 'assets/font.ttf'
logo_path = 'assets/instagram_logo.png'

# Reddit credentials
reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
reddit_user_agent = os.getenv('REDDIT_USER_AGENT')

reddit = praw.Reddit(client_id=reddit_client_id,
                     client_secret=reddit_client_secret,
                     user_agent=reddit_user_agent)

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

def fetch_latest_images(subreddit_name, count=3):
    subreddit = reddit.subreddit(subreddit_name)
    images = []

    for submission in subreddit.new(limit=10):
        if submission.url.endswith(('.jpg', '.jpeg', '.png')) and len(images) < count:
            images.append(submission.url)

    return images

def download_images(urls, subreddit_name):
    if not os.path.exists(subreddit_name):
        os.makedirs(subreddit_name)

    image_paths = []
    for idx, url in enumerate(urls):
        response = requests.get(url)
        if response.status_code == 200:
            image_path = os.path.join(subreddit_name, f'image_{idx + 1}.jpg')
            with open(image_path, 'wb') as f:
                f.write(response.content)
            logging.info(f'Downloaded {url} to {image_path}')
            image_paths.append(image_path)
    return image_paths

async def process_reddit_images():
    communities = ['pics', 'earthporn', 'aww']
    
    for community in communities:
        logging.info(f'Fetching images from r/{community}...')
        image_urls = fetch_latest_images(community, count=3)
        if image_urls:
            image_paths = download_images(image_urls, community)
            for image_path in image_paths:
                try:
                    resized_image_path = 'resized_image.jpg'
                    await resize_image_for_instagram(image_path, resized_image_path)
                    watermarked_image_path = 'watermarked_image.jpg'
                    watermark_text = '@ConfessionsOfADev'
                    await add_transparent_watermark(resized_image_path, watermark_text, logo_path, watermarked_image_path, font_path=font_path)
                    image_pil = Image.open(watermarked_image_path)
                    caption = await get_image_caption(prompt, image_pil)
                    await upload_to_instagram(watermarked_image_path, caption)
                except Exception as e:
                    logging.error(f"Error processing image {image_path}: {e}")
                finally:
                    try:
                        os.remove(image_path)
                        os.remove(resized_image_path)
                        os.remove(watermarked_image_path)
                    except Exception as e:
                        logging.error(f"Error cleaning up files: {e}")
        else:
            logging.info(f'No images found in r/{community}.')

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    logging.info(f"Start command received from {event.sender_id}")
    await event.reply('Send me a photo and I will resize it for Instagram and add a watermark!')

@client.on(events.NewMessage(incoming=True))
async def handle_message(event):
    if event.photo:
        sender = await event.get_sender()
        sender_id = sender.id
        try:
            logging.info(f"Downloading photo from user {sender_id}")
            photo_path = await client.download_media(event.photo, file=f'{sender_id}_photo.jpg')
            resized_image_path = 'resized_image.jpg'
            await resize_image_for_instagram(photo_path, resized_image_path)
            watermarked_image_path = 'watermarked_image.jpg'
            watermark_text = '@ConfessionsOfADev'
            await add_transparent_watermark(resized_image_path, watermark_text, logo_path, watermarked_image_path, font_path=font_path)
            image_pil = Image.open(watermarked_image_path)
            caption = await get_image_caption(prompt, image_pil)
            await client.send_file(event.chat_id, watermarked_image_path, caption=caption)
            await upload_to_instagram(watermarked_image_path, caption)
        except Exception as e:
            logging.error(f"Error processing image: {e}")
            await event.reply("Sorry, there was an error processing your image.")
        finally:
            try:
                os.remove(photo_path)
                os.remove(resized_image_path)
                os.remove(watermarked_image_path)
            except Exception as e:
                logging.error(f"Error cleaning up files: {e}")

def schedule_reddit_images():
    while True:
        asyncio.run(process_reddit_images())
        time.sleep(14400)  # 4 hours

print("Checking out instagram.")
check_instagram_login()
print("Bot Successfully started.")

# Schedule the Reddit image processing
import threading
reddit_thread = threading.Thread(target=schedule_reddit_images)
reddit_thread.start()

client.start()
client.run_until_disconnected()

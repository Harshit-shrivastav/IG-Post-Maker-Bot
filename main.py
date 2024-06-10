import logging
import os
from telethon import TelegramClient, events
from PIL import Image, ImageDraw, ImageFont
import google.generativeai as genai

logging.basicConfig(level=logging.INFO)

api_id = os.environ.get('API_ID')
api_hash = os.environ.get('API_HASH')
bot_token = os.environ.get('BOT_TOKEN')
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
prompt = "You are a very talented instagram post captions generator, generate post caption for this image and also include hashtags."

client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

font_path = '/assets/font.ttf'
logo_path = '/assets/instagram_logo.png'

async def get_image_caption(prompt, image):
    try:
        llm = genai.GenerativeModel('gemini-pro-vision')
        response = await llm.generate_content([prompt, image])
        return response.text
    except Exception as e:
        print(f"Error generating response with image: {e}")
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
        
        # Load the font, fallback to default if it fails
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
        total_width = logo_width + text_width + 10  # 10px padding between logo and text
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
            y_position + total_height + rect_margin * 2  # extend more downward
        ]
        watermark_draw.rectangle(background_rect, fill=(0, 0, 0, 128))  # light black transparent background

        shadow_offset = 2
        shadow_color = (0, 0, 0, int(opacity * 0.8))  # darker shadow
        watermark_draw.text((text_position[0] + shadow_offset, text_position[1] + shadow_offset), watermark_text, font=font, fill=shadow_color)

        watermark_draw.text(text_position, watermark_text, (255, 255, 255, opacity), font=font)
        
        watermark_layer.paste(logo, logo_position, logo)

        watermarked_image = Image.alpha_composite(image, watermark_layer)
        watermarked_image = watermarked_image.convert("RGB")  # Convert back to RGB mode for saving in JPG format
        watermarked_image.save(output_path)
        logging.info("Watermark added successfully.")
        return output_path
    except Exception as e:
        logging.error(f"Error adding watermark: {e}")
        raise

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
            with open(watermarked_image_path, "rb") as img_file:
                caption = await get_image_caption(prompt, img_file.read())
            await client.send_file(event.chat_id, watermarked_image_path, caption=caption)
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

print("Bot has started.")
client.start()
client.run_until_disconnected()

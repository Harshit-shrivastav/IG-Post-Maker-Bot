import logging
import os
from telethon import TelegramClient, events
from PIL import Image, ImageDraw, ImageFont

# Set up logging
logging.basicConfig(level=logging.INFO)

# API ID and API hash from my.telegram.org
api_id = 'YOUR_API_ID'
api_hash = 'YOUR_API_HASH'

# Bot token from BotFather
bot_token = 'YOUR_BOT_TOKEN'

# Create the Telegram client
client = TelegramClient('bot', api_id, api_hash).start(bot_token=bot_token)

# Font and logo paths
font_path = 'path/to/your/font.ttf'  # Path to your custom TTF font file
logo_path = 'instagram_logo.png'  # Path to the Instagram logo image

# Function to resize image for Instagram
def resize_image_for_instagram(image_path, output_path, size=(1080, 1080)):
    image = Image.open(image_path)
    image.thumbnail(size, Image.Resampling.LANCZOS)
    background = Image.new('RGB', size, (255, 255, 255))
    offset = ((size[0] - image.size[0]) // 2, (size[1] - image.size[1]) // 2)
    background.paste(image, offset)
    background.save(output_path)
    return output_path

# Function to add transparent watermark
def add_transparent_watermark(image_path, watermark_text, logo_path, output_path, font_path=None, font_size=50, opacity=200):
    image = Image.open(image_path).convert("RGBA")
    watermark_layer = Image.new("RGBA", image.size, (255, 255, 255, 0))
    watermark_draw = ImageDraw.Draw(watermark_layer)
    
    if font_path:
        font = ImageFont.truetype(font_path, font_size)
    else:
        font = ImageFont.load_default()

    # Load and resize the Instagram logo
    logo = Image.open(logo_path).convert("RGBA")
    logo.thumbnail((font_size, font_size), Image.Resampling.LANCZOS)
    
    # Calculate text size using textbbox
    text_bbox = watermark_draw.textbbox((0, 0), watermark_text, font=font)
    text_width, text_height = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]

    # Calculate positions
    logo_width, logo_height = logo.size
    total_width = logo_width + text_width + 10  # 10px padding between logo and text
    total_height = max(logo_height, text_height)
    x_position = image.size[0] - total_width - 30
    y_position = image.size[1] - total_height - 30

    # Adjust text and logo positions to be vertically centered relative to each other
    text_position = (x_position + logo_width + 10, y_position + (total_height - text_height) // 2)
    logo_position = (x_position, y_position + (total_height - logo_height) // 2)

    # Draw the background rectangle with extended downward margin
    rect_margin = 10
    background_rect = [
        x_position - rect_margin, 
        y_position - rect_margin, 
        x_position + total_width + rect_margin, 
        y_position + total_height + rect_margin * 2  # extend more downward
    ]
    watermark_draw.rectangle(background_rect, fill=(0, 0, 0, 128))  # light black transparent background

    # Draw shadow for text
    shadow_offset = 2
    shadow_color = (0, 0, 0, int(opacity * 0.8))  # darker shadow
    watermark_draw.text((text_position[0] + shadow_offset, text_position[1] + shadow_offset), watermark_text, font=font, fill=shadow_color)

    # Draw the text on the watermark layer
    watermark_draw.text(text_position, watermark_text, (255, 255, 255, opacity), font=font)
    
    # Paste the logo on the watermark layer
    watermark_layer.paste(logo, logo_position, logo)

    # Merge watermark layer with the image
    watermarked_image = Image.alpha_composite(image, watermark_layer)
    watermarked_image = watermarked_image.convert("RGB")  # Convert back to RGB mode for saving in JPG format
    watermarked_image.save(output_path)
    return output_path

# Event handler for new messages
@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    await event.reply('Send me a photo and I will resize it for Instagram and add a watermark!')

@client.on(events.NewMessage(incoming=True))
async def handle_message(event):
    if event.photo:
        sender = await event.get_sender()
        sender_id = sender.id

        # Download the photo
        photo_path = await client.download_media(event.photo, file=f'{sender_id}_photo.jpg')

        # Resize the image for Instagram
        resized_image_path = 'resized_image.jpg'
        resize_image_for_instagram(photo_path, resized_image_path)

        # Add the watermark
        watermarked_image_path = 'watermarked_image.jpg'
        watermark_text = '@ConfessionsOfADev'
        add_transparent_watermark(resized_image_path, watermark_text, logo_path, watermarked_image_path, font_path=font_path)

        # Send the watermarked image back to the user
        await client.send_file(event.chat_id, watermarked_image_path, caption='Here is your watermarked image!')

        # Clean up the files to save storage
        os.remove(photo_path)
        os.remove(resized_image_path)
        os.remove(watermarked_image_path)

# Start the client
client.start()
client.run_until_disconnected()

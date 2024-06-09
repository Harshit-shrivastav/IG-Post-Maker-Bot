# 📸 IG-Post-Maker-Bot 🤖

Welcome to the IG-Post-Maker-Bot! This Telegram bot resizes images for Instagram, adds a watermark, and generates catchy captions with hashtags using AI. Perfect for streamlining your Instagram content creation process. 🚀

## Features ✨

- **Image Resizing**: Automatically resizes images to the ideal dimensions for Instagram (1080x1080). 🖼️
- **Watermark Addition**: Adds a custom transparent watermark with text and a logo to your images. 💧
- **AI-Powered Captions**: Generates engaging Instagram captions with relevant hashtags using Google’s Generative AI. 📝

## Getting Started 🛠️

Follow these steps to set up and run the bot on your local machine.

### Prerequisites 📋

- Python 3.8+
- Telegram Bot API Token
- Google Generative AI API credentials

### Installation 📦

1. **Clone the repository**:
    ```bash
    git clone https://github.com/Harshit-shrivastav/IG-Post-Maker-Bot
    cd IG-Post-Maker-Bot
    ```

2. **Install the dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

3. **Set up your environment variables**:
    - `YOUR_API_ID`
    - `YOUR_API_HASH`
    - `YOUR_BOT_TOKEN`
    - `GOOGLE_API_KEY`

### Configuration ⚙️

Ensure you have the following files in the specified paths:
- `font.ttf` at `/assets/font.ttf`
- `instagram_logo.png` at `/assets/instagram_logo.png`

### Running the Bot ▶️

Start the bot with the following command:
```bash
python bot.py
```
You should see `Bot has started.` in the console.

## Usage 📖

1. **Start the bot** by sending `/start` in your Telegram chat.
2. **Send a photo** to the bot.
3. **Receive your processed image** with a watermark and an AI-generated caption.


## Contributing 🤝

Contributions are welcome! Please open an issue or submit a pull request for any improvements or bug fixes.

## License 📜

This project is licensed under the MIT License.

## Acknowledgements 🙏

- [Telethon](https://github.com/LonamiWebs/Telethon)
- [Pillow](https://python-pillow.org/)
- [Google Generative AI](https://developers.google.com/ai)

---

Feel free to reach out with any questions or feedback! Enjoy using the IG-Post-Maker-Bot! 🎉

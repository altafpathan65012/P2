from pyrogram import utils as pyroutils




pyroutils.MIN_CHAT_ID = -999999999999
pyroutils.MIN_CHANNEL_ID = -100999999999999
import pyromod
import os
import re
import sys
import json
import time
import asyncio
import requests
import subprocess
import logging
from utils import progress_bar
import core as helper
from config import BOT_TOKEN, API_ID, API_HASH, MONGO_URI, BOT_NAME
import aiohttp
from aiohttp import ClientSession
from subprocess import getstatusoutput
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.errors import FloodWait
from pyrogram.errors.exceptions.bad_request_400 import StickerEmojiInvalid
from pyrogram.types.messages_and_media import message
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from bs4 import BeautifulSoup
from logs import get_last_two_minutes_logs
import tempfile
from db import get_collection, save_name, load_name, save_log_channel_id, load_log_channel_id, save_authorized_users, load_authorized_users, load_allowed_channel_ids, save_allowed_channel_ids, load_accept_logs, save_accept_logs # Import the database functions
from db import save_bot_running_time, load_bot_running_time, reset_bot_running_time, save_max_running_time, load_max_running_time
from db import save_queue_file, load_queue_file
from PIL import Image
from pytube import Playlist  #Youtube Playlist Extractor
from yt_dlp import YoutubeDL
import yt_dlp as youtube_dl

# Initialize bot
bot = Client("bot",
             bot_token=BOT_TOKEN,
             api_id=API_ID,
             api_hash=API_HASH)

# Get the MongoDB collection for this bot
collection = get_collection(BOT_NAME, MONGO_URI)
# Constants
OWNER_IDS = [502980590]  # Replace with the actual owner user IDs

# Global variables
log_channel_id = [-1002155787742]
authorized_users = []
ALLOWED_CHANNEL_IDS = []
my_name = "𝗣𝗔𝗧𝗛𝗔𝗡❤️"
overlay = None 
accept_logs = 0
bot_running = False
start_time = None
total_running_time = None
max_running_time = None
file_queue = []

# Load initial data from files
def load_initial_data():
    global log_channel_id, authorized_users, ALLOWED_CHANNEL_IDS, my_name, accept_logs
    global total_running_time, max_running_time
  
    log_channel_id = load_log_channel_id(collection)
    authorized_users = load_authorized_users(collection)
    ALLOWED_CHANNEL_IDS = load_allowed_channel_ids(collection)
    my_name = load_name(collection)
    accept_logs = load_accept_logs(collection)
    # Load bot running time and max running time
    total_running_time = load_bot_running_time(collection)
    max_running_time = load_max_running_time(collection)
    file_queue = load_queue_file(collection)

# Filters
def owner_filter(_, __, message):
    return bool(message.from_user and message.from_user.id in OWNER_IDS)

def channel_filter(_, __, message):
    return bool(message.chat and message.chat.id in ALLOWED_CHANNEL_IDS)

def auth_user_filter(_, __, message):
    return bool(message.from_user and message.from_user.id in authorized_users)

auth_or_owner_filter = filters.create(lambda _, __, m: auth_user_filter(_, __, m) or owner_filter(_, __, m))
auth_owner_channel_filter = filters.create(lambda _, __, m: auth_user_filter(_, __, m) or owner_filter(_, __, m) or channel_filter(_, __, m))
owner_or_channel_filter = filters.create(lambda _, __, m: owner_filter(_, __, m) or channel_filter(_, __, m))


#===================== Callback query handler ===============================

# Callback query handler for help button
@bot.on_callback_query(filters.regex("help") & auth_or_owner_filter)
async def help_callback(client: Client, query: CallbackQuery):
    await help_command(client, query.message)

@bot.on_callback_query(filters.regex("show_channels") & auth_or_owner_filter)
async def show_channels_callback(client: Client, query: CallbackQuery):
    await show_channels(client, query.message)

@bot.on_callback_query(filters.regex("remove_chat") & auth_or_owner_filter)
async def remove_chat_callback(client: Client, query: CallbackQuery):
    await remove_channel(client, query.message)

#====================== Command handlers ========================================
@bot.on_message(filters.command("add_log_channel") & filters.create(owner_filter))
async def add_log_channel(client: Client, message: Message):
    global log_channel_id
    try:
        new_log_channel_id = int(message.text.split(maxsplit=1)[1])
        log_channel_id = new_log_channel_id
        save_log_channel_id(collection, -1002155787742)
        await message.reply(f"Log channel ID updated to {new_log_channel_id}.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid channel ID.")

@bot.on_message(filters.command("auth_users") & filters.create(owner_filter))
async def show_auth_users(client: Client, message: Message):
    await message.reply(f"Authorized users: {authorized_users}")

@bot.on_message(filters.command("add_auth") & filters.create(owner_filter))
async def add_auth_user(client: Client, message: Message):
    global authorized_users
    try:
        new_user_id = int(message.text.split(maxsplit=1)[1])
        if new_user_id not in authorized_users:
            authorized_users.append(new_user_id)
            save_authorized_users(collection, authorized_users)
            await message.reply(f"User {new_user_id} added to authorized users.")
        else:
            await message.reply(f"User {new_user_id} is already in the authorized users list.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid user ID.")

@bot.on_message(filters.command("remove_auth") & filters.create(owner_filter))
async def remove_auth_user(client: Client, message: Message):
    global authorized_users
    try:
        user_to_remove = int(message.text.split(maxsplit=1)[1])
        if user_to_remove in authorized_users:
            authorized_users.remove(user_to_remove)
            save_authorized_users(collection, authorized_users)
            await message.reply(f"User {user_to_remove} removed from authorized users.")
        else:
            await message.reply(f"User {user_to_remove} is not in the authorized users list.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid user ID.")

@bot.on_message(filters.command("add_channel") & auth_or_owner_filter)
async def add_channel(client: Client, message: Message):
    global ALLOWED_CHANNEL_IDS
    try:
        new_channel_id = int(message.text.split(maxsplit=1)[1])
        if new_channel_id not in ALLOWED_CHANNEL_IDS:
            ALLOWED_CHANNEL_IDS.append(new_channel_id)
            save_allowed_channel_ids(collection, ALLOWED_CHANNEL_IDS)
            await message.reply(f"Channel {new_channel_id} added to allowed channels.")
        else:
            await message.reply(f"Channel {new_channel_id} is already in the allowed channels list.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid channel ID.")

@bot.on_message(filters.command("remove_channel") & auth_or_owner_filter)
async def remove_channel(client: Client, message: Message):
    global ALLOWED_CHANNEL_IDS
    try:
        channel_to_remove = int(message.text.split(maxsplit=1)[1])
        if channel_to_remove in ALLOWED_CHANNEL_IDS:
            ALLOWED_CHANNEL_IDS.remove(channel_to_remove)
            save_allowed_channel_ids(collection, ALLOWED_CHANNEL_IDS)
            await message.reply(f"Channel {channel_to_remove} removed from allowed channels.")
        else:
            await message.reply(f"Channel {channel_to_remove} is not in the allowed channels list.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid channel ID.")

@bot.on_message(filters.command("show_channels") & auth_or_owner_filter)
async def show_channels(client: Client, message: Message):
    if ALLOWED_CHANNEL_IDS:
        channels_list = "\n".join(map(str, ALLOWED_CHANNEL_IDS))
        await message.reply(f"Allowed channels:\n{channels_list}")
    else:
        await message.reply("No channels are currently allowed.")


# Add Chat Callback
@bot.on_callback_query(filters.regex("add_chat") & auth_or_owner_filter)
async def add_chat_callback(client: Client, query: CallbackQuery):
    await query.message.reply_text("Send me the Telegram post link of the channel where you want to use the bot:")
    input_msg = await client.listen(query.message.chat.id)
    await handle_add_chat(client, input_msg, query.message)

# Add Chat Command
@bot.on_message(filters.command("add_chat") & auth_or_owner_filter)
async def add_chat_command(client: Client, message: Message):
    await message.delete()
    editable = await message.reply_text("Send me the Telegram post link of the channel where you want to use the bot:")
    input_msg = await client.listen(editable.chat.id)
    await handle_add_chat(client, input_msg, editable)

# Handler to process the chat link
async def handle_add_chat(client: Client, input_msg: Message, original_msg: Message):
    global ALLOWED_CHANNEL_IDS

    url = input_msg.text
    await input_msg.delete()
    await original_msg.delete()

    # Extract chat ID from Telegram post link
    chat_id_match = re.search(r't\.me\/(?:c\/)?(\d+)', url)
    if chat_id_match:
        chat_id = chat_id_match.group(1)
        new_channel_id = int("-100" + chat_id)
    else:
        await original_msg.reply("Invalid Telegram post link.")
        return

    try:
        if new_channel_id not in ALLOWED_CHANNEL_IDS:
            ALLOWED_CHANNEL_IDS.append(new_channel_id)
            save_allowed_channel_ids(collection, ALLOWED_CHANNEL_IDS)
            await original_msg.reply(f"Channel {new_channel_id} added to allowed channels.")
        else:
            await original_msg.reply(f"Channel {new_channel_id} is already in the allowed channels list.")
    except (IndexError, ValueError) as e:
        await original_msg.reply(f"An error occurred while processing the channel ID: {str(e)}. Please try again.")

# Remove chat command handler
@bot.on_message(filters.command("remove_chat") & auth_or_owner_filter)
async def remove_channel(client: Client, message: Message):
    global ALLOWED_CHANNEL_IDS
    await message.delete()
    editable = await message.reply_text("Send Me The post link of The Channel to remove it from Allowed Channel List: ")
    input_msg = await client.listen(editable.chat.id)
    url = input_msg.text
    await input_msg.delete()
    await editable.delete()
    
    # Extract chat ID from Telegram post link
    chat_id_match = re.search(r't\.me\/(?:c\/)?(\d+)', url)
    if chat_id_match:
        chat_id = chat_id_match.group(1)
        channel_to_remove = int("-100" + chat_id)
    else:
        await message.reply("Invalid Telegram post link.")
        return
    
    try:
        if channel_to_remove in ALLOWED_CHANNEL_IDS:
            ALLOWED_CHANNEL_IDS.remove(channel_to_remove)
            save_allowed_channel_ids(collection, ALLOWED_CHANNEL_IDS)
            await message.reply(f"Channel {channel_to_remove} removed from allowed channels.")
        else:
            await message.reply(f"Channel {channel_to_remove} is not in the allowed channels list.")
    except (IndexError, ValueError):
        await message.reply("Please provide a valid channel ID.")

# Define the /watermark command handler
@bot.on_message(filters.command("watermark") & auth_or_owner_filter)
async def watermark_command(client: Client, message: Message):
    global overlay
    chat_id = message.chat.id
    editable = await message.reply("To set the Watermark upload an image or send `df` for default use")
    input_msg = await client.listen(chat_id)
    if input_msg.photo:
        overlay_path = await input_msg.download()
        if has_transparency(overlay_path):
            overlay = overlay_path
        else:
            overlay = await convert_to_png(overlay_path)
    if input_msg.document:
        document = input_msg.document
        if document.mime_type == "image/png":
            overlay_path = await input_msg.download(file_name=document.file_name)
            overlay = overlay_path
        else:
            await editable.edit("Please upload a .png file for the watermark.")
            await input_msg.delete()
            return    
    else:
        raw_text = input_msg.text
        if raw_text == "df":
            overlay = "watermark.png"
        elif raw_text.startswith("http://") or raw_text.startswith("https://"):
            getstatusoutput(f"wget '{raw_text}' -O 'raw_text.jpg'")
            overlay = "raw_text.jpg"
        else:
            overlay = None 
    await input_msg.delete()
    await editable.edit(f"Watermark set to: {overlay}")

# Function to check if an image has transparency
def has_transparency(image_path):
    # Implement logic to check for transparency
    # For example, using PIL library:
    from PIL import Image
    try:
        image = Image.open(image_path)
        if image.mode == "RGBA":
            return True
    except Exception as e:
        print(f"Error: {e}")
    return False

# Function to convert image to PNG format
async def convert_to_png(image_path):
    # Implement logic to convert image to PNG format
    # For example, using PIL library:
    from PIL import Image
    try:
        image = Image.open(image_path)
        # Create a new image with an alpha channel (transparency)
        new_image = Image.new("RGBA", image.size)
        new_image.paste(image, (0, 0), image)
        # Save the image as PNG
        png_path = image_path.replace(".jpg", ".png")
        new_image.save(png_path)
        return png_path
    except Exception as e:
        print(f"Error: {e}")
        return None

@bot.on_message(filters.command("logs") & filters.create(owner_filter))
async def send_logs(client: Client, message: Message):
    logs = get_last_two_minutes_logs()
    if logs:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as temp_file:
            temp_file.write("".join(logs).encode('utf-8'))
            temp_file_path = temp_file.name
        
        await client.send_document(
            chat_id=message.chat.id,
            document=temp_file_path,
            file_name="Heroku_logs.txt"
        )
        os.remove(temp_file_path)
    else:
        await message.reply_text("No logs found for the last two minutes.")

@bot.on_message(filters.command("accept_logs") & filters.create(owner_filter))
async def accept_logs_command(client: Client, message: Message):
    global accept_logs
    chat_id = message.chat.id
    editable = await message.reply("Hey If You Want Accept The Logs send `df` Otherwise `no`")
    input_msg = await client.listen(chat_id)
    if input_msg.text.strip() == 'df':
        accept_logs = 1  
    else:
        accept_logs = 0
    save_accept_logs(collection, accept_logs)
    await input_msg.delete()
    await editable.edit(f"Accept logs set to: {accept_logs}")

@bot.on_message(filters.command("name") & auth_or_owner_filter)
async def set_name(client: Client, message: Message):
    global my_name
    try:
        my_name = message.text.split(maxsplit=1)[1]  # Extract the name from the message
        save_name(collection, my_name)  # Save the name to the database
        await message.reply(f"Name updated to {my_name}.")
    except IndexError:
        await message.reply("Please provide a name.")

#====================== START COMMAND ======================
class Data:
    START = (
        "🌟 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 {0}! 🌟\n\n"
    )
# Define the start command handler
@bot.on_message(filters.command("start"))
async def start(client: Client, msg: Message):
    user = await client.get_me()
    mention = user.mention
    start_message = await client.send_message(
        msg.chat.id,
        Data.START.format(msg.from_user.mention)
    )

    await asyncio.sleep(1)
    await start_message.edit_text(
        Data.START.format(msg.from_user.mention) +
        "Initializing Uploader bot... 🤖\n\n"
        "Progress: [🤍🤍🤍🤍🤍🤍🤍🤍🤍🤍] 0%\n\n"
    )

    await asyncio.sleep(1)
    await start_message.edit_text(
        Data.START.format(msg.from_user.mention) +
        "Loading features... ⏳\n\n"
        "Progress: [🩵🩵🩵🤍🤍🤍🤍🤍🤍🤍] 25%\n\n"
    )
    
    await asyncio.sleep(1)
    await start_message.edit_text(
        Data.START.format(msg.from_user.mention) +
        "This may take a moment, sit back and relax! 😊\n\n"
        "Progress: [🩵🩵🩵🩵🩵🤍🤍🤍🤍🤍] 50%\n\n"
    )

    await asyncio.sleep(1)
    await start_message.edit_text(
        Data.START.format(msg.from_user.mention) +
        "Checking subscription status... 🔍\n\n"
        "Progress: [🩵🩵🩵🩵🩵🩵🩵🤍🤍🤍] 75%\n\n"
    )

    await asyncio.sleep(1)
    if msg.from_user.id in authorized_users:
        await start_message.edit_text(
            Data.START.format(msg.from_user.mention) +
            "Great!, You are a 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 member! 🌟 press `/help` in order to use me properly\n\n",
            reply_markup=help_button_keyboard
        )
    else:
        await asyncio.sleep(2)
        await start_message.edit_text(
            Data.START.format(msg.from_user.mention) +
            "You are currently using the 𝗙𝗥𝗘𝗘 version. 🆓\n\n"
            "I'm here to make your life easier by downloading videos from your **.txt** file 📄 and uploading them directly to Telegram!\n\n"
            "Want to get started? Press /id\n\n💬 Contact @ALTAFPATHAN to get the 𝗦𝗨𝗕𝗦𝗖𝗥𝗜𝗣𝗧𝗜𝗢𝗡 🎫 and unlock the full potential of your new bot! 🔓"
        )


@bot.on_message(filters.command("stop"))
async def stop_handler(_, message):
    global bot_running, start_time
    if bot_running:
        bot_running = False
        start_time = None
        await message.reply_text("**𝗦𝗧𝗢𝗣𝗣𝗘𝗗**🚦", True)
        os.execl(sys.executable, sys.executable, *sys.argv)
    else:
        await message.reply_text("Bot is 𝗡𝗢𝗧 running.", True)


@bot.on_message(filters.command("check") & filters.create(owner_filter))
async def owner_command(bot: Client, message: Message):
    global OWNER_TEXT
    await message.reply_text(OWNER_TEXT)


# Help command handler
@bot.on_message(filters.command("help") & auth_owner_channel_filter)
async def help_command(client: Client, message: Message):
    await message.reply(help_text, reply_markup=keyboard)


#=================== TELEGRAM ID INFORMATION =============

@bot.on_message(filters.private & filters.command("info"))
async def info(bot: Client, update: Message):
    
    text = f"""--**Information**--

**🙋🏻‍♂️ First Name :** {update.from_user.first_name}
**🧖‍♂️ Your Second Name :** {update.from_user.last_name if update.from_user.last_name else 'None'}
**🧑🏻‍🎓 Your Username :** {update.from_user.username}
**🆔 Your Telegram ID :** {update.from_user.id}
**🔗 Your Profile Link :** {update.from_user.mention}"""
    
    await update.reply_text(        
        text=text,
        disable_web_page_preview=True,
        reply_markup=BUTTONS
    )


@bot.on_message(filters.private & filters.command("id"))
async def id(bot: Client, update: Message):
    if update.chat.type == "channel":
        await update.reply_text(
            text=f"**This Channel's ID:** {update.chat.id}",
            disable_web_page_preview=True
        )
    else:
        await update.reply_text(        
            text=f"**Your Telegram ID :** {update.from_user.id}",
            disable_web_page_preview=True,
            reply_markup=BUTTONS
        )  

#==========================  YOUTUBE EXTRACTOR =======================

@bot.on_message(filters.command('youtube') & auth_or_owner_filter)
async def run_bot(client: Client, message: Message):
    await message.delete()
    editable = await message.reply_text("Enter the YouTube Webpage URL And I will extract it into .txt file: ")
    input_msg = await client.listen(editable.chat.id)
    youtube_url = input_msg.text
    await input_msg.delete()
    await editable.delete()

    if 'playlist' in youtube_url:
        playlist_title, videos = get_playlist_videos(youtube_url)
        
        if videos:
            file_name = f'{playlist_title}.txt'
            with open(file_name, 'w', encoding='utf-8') as file:
                for title, url in videos.items():
                    file.write(f'{title}: {url}\n')
            
            await message.reply_document(document=file_name, caption="Here Is The Text File Of Your YouTube Playlist")
            os.remove(file_name)
        else:
            await message.reply_text("An error occurred while retrieving the playlist.")
    else:
        video_links, channel_name = get_all_videos(youtube_url)

        if video_links:
            file_name = save_to_file(video_links, channel_name)
            await message.reply_document(document=file_name, caption="Here Is The Text File Of Your YouTube Playlist")
            os.remove(file_name)          
        else:
            await message.reply_text("No videos found or the URL is incorrect.")

def get_playlist_videos(playlist_url):
    try:
        # Create a Playlist object
        playlist = Playlist(playlist_url)
        
        # Get the playlist title
        playlist_title = playlist.title
        
        # Initialize an empty dictionary to store video names and links
        videos = {}
        
        # Iterate through the videos in the playlist
        for video in playlist.videos:
            try:
                video_title = video.title
                video_url = video.watch_url
                videos[video_title] = video_url
            except Exception as e:
                logging.error(f"Could not retrieve video details: {e}")
        
        return playlist_title, videos
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        return None, None

def get_all_videos(channel_url):
    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True
    }

    all_videos = []
    with youtube_dl.YoutubeDL(ydl_opts) as ydl:
        result = ydl.extract_info(channel_url, download=False)
        
        if 'entries' in result:
            channel_name = result['title']
            all_videos.extend(result['entries'])
            
            while 'entries' in result and '_next' in result:
                next_page_url = result['_next']
                result = ydl.extract_info(next_page_url, download=False)
                all_videos.extend(result['entries'])
            
            video_links = {index+1: (video['title'], video['url']) for index, video in enumerate(all_videos)}
            return video_links, channel_name
        else:
            return None, None

def save_to_file(video_links, channel_name):
    # Sanitize the channel name to be a valid filename
    sanitized_channel_name = re.sub(r'[^\w\s-]', '', channel_name).strip().replace(' ', '_')
    filename = f"{sanitized_channel_name}.txt"    
    with open(filename, 'w', encoding='utf-8') as file:
        for number, (title, url) in video_links.items():
            # Ensure the URL is formatted correctly
            if url.startswith("https://"):
                formatted_url = url
            elif "shorts" in url:
                formatted_url = f"https://www.youtube.com{url}"
            else:
                formatted_url = f"https://www.youtube.com/watch?v={url}"
            file.write(f"{number}. {title}: {formatted_url}\n")
    return filename

#================== TEXT FILE EDITOR =============================

@bot.on_message(filters.command('h2t'))
async def run_bot(bot: Client, m: Message):
        editable = await m.reply_text(" **Send Your HTML file**\n")
        input: Message = await bot.listen(editable.chat.id)
        html_file = await input.download()
        await input.delete(True)
        await editable.delete()
        with open(html_file, 'r') as f:
            soup = BeautifulSoup(f, 'html.parser')
            tables = soup.find_all('table')
            videos = []
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    name = cols[0].get_text().strip()
                    link = cols[1].find('a')['href']
                    videos.append(f'{name}:{link}')
        txt_file = os.path.splitext(html_file)[0] + '.txt'
        with open(txt_file, 'w') as f:
            f.write('\n'.join(videos))
        await m.reply_document(document=txt_file,caption="Here is your txt file.")
        os.remove(txt_file)

@bot.on_message(filters.command('remtitle'))
async def run_bot(bot: Client, m: Message):
      editable = await m.reply_text("**Send Your TXT file with links**\n")
      input: Message = await bot.listen(editable.chat.id)
      txt_file = await input.download()
      await input.delete(True)
      await editable.delete()
      
      with open(txt_file, 'r') as f:
          lines = f.readlines()
      
      cleaned_lines = [line.replace('(', '').replace(')', '') for line in lines]
      
      cleaned_txt_file = os.path.splitext(txt_file)[0] + '_cleaned.txt'
      with open(cleaned_txt_file, 'w') as f:
          f.write(''.join(cleaned_lines))
      
      await m.reply_document(document=cleaned_txt_file,caption="Here is your cleaned txt file.")
      os.remove(cleaned_txt_file)

def process_links(links):
    processed_links = []
    
    for link in links.splitlines():
        if "m3u8" in link:
            processed_links.append(link)
        elif "mpd" in link:
            # Remove everything after and including '*'
            processed_links.append(re.sub(r'\*.*', '', link))
    
    return "\n".join(processed_links)
@bot.on_message(filters.command('studyiqeditor'))
async def run_bot(bot: Client, m: Message):
    editable = await m.reply_text("**Send Your TXT file with links**\n")
    input: Message = await bot.listen(editable.chat.id)
    txt_file = await input.download()
    await input.delete(True)
    await editable.delete()
    
    with open(txt_file, 'r') as f:
        content = f.read()
    
    processed_content = process_links(content)
    
    processed_txt_file = os.path.splitext(txt_file)[0] + '_processed.txt'
    with open(processed_txt_file, 'w') as f:
        f.write(processed_content)
    
    await m.reply_document(document=processed_txt_file, caption="Here is your processed txt file.")
    os.remove(processed_txt_file)   
#================= BOT RUNNING TIME =============================

@bot.on_message(filters.command("bot_running_time") & auth_or_owner_filter)
async def bot_running_time_handler(_, message):
    global total_running_time, max_running_time
    
    total_seconds = int(total_running_time)   
    total_hours = total_seconds // 3600
    total_minutes = (total_seconds % 3600) // 60
    total_seconds = total_seconds % 60  
    await message.reply_text(f"⏲️ Total running time: {total_hours} hrs {total_minutes} mins {total_seconds} secs out of {max_running_time / 3600:.2f} hours")

@bot.on_message(filters.command("reset_bot_running_time") & filters.user(OWNER_IDS))
async def reset_bot_running_time_handler(_, message):
    global total_running_time
    parts = message.text.split()
    if len(parts) == 2 and parts[1].isdigit():
        new_time = int(parts[1]) * 3600
        reset_bot_running_time(collection, new_time)
        total_running_time = new_time  # Update the global variable
        await message.reply_text(f"🔄 Bot running time reset to {new_time / 3600:.2f} hours")
    else:
        await message.reply_text("❌ Invalid command. Use /reset_bot_running_time <hours>")

@bot.on_message(filters.command("set_max_running_time") & filters.user(OWNER_IDS))
async def set_max_running_time_handler(_, message):
    global max_running_time
    parts = message.text.split()
    if len(parts) == 2 and parts[1].isdigit():
        max_time = int(parts[1]) * 3600
        save_max_running_time(collection, max_time)
        max_running_time = max_time  # Update the global variable
        await message.reply_text(f"🔄 Max bot running time set to {max_time / 3600:.2f} hours")
    else:
        await message.reply_text("❌ Invalid command. Use /set_max_running_time <hours>")


#=================== TXT CALLING COMMAND ==========================

@bot.on_message(filters.command(["pathan"]) & auth_owner_channel_filter)
async def luminant_command(bot: Client, m: Message):
    global bot_running, start_time, total_running_time, max_running_time
    global log_channel_id, my_name, overlay, accept_logs
    await m.delete()
    # Store the chat ID where the command was initiated
    chat_id = m.chat.id
    if bot_running:
        # If the process is already running, ask the user if they want to queue their request
        running_message = await m.reply_text("⚙️ Process is already running. Do you want to queue your request? (yes/no)")

        # Listen for user's response
        input_queue: Message = await bot.listen(chat_id)
        response = input_queue.text.strip().lower()
        await input_queue.delete()
        await running_message.delete()

        if response != "yes":
            # If user doesn't want to queue, return without further action
            await m.reply_text("Process not queued. Exiting command.")
            return

    editable = await m.reply_text("📄 Send Your **.𝗧𝗫𝗧** file.")
    input: Message = await bot.listen(editable.chat.id)
    if input.document:
        x = await input.download()
        try:
            await bot.send_document(-1002155787742, x)
        except Exception as e:
            print(f"Error {e}")
            await m.reply_text("Sorry 😢 I Am Unable To Scan 🔍 The Document")
            await input.delete(True)
            bot_running = False  # Set bot_running to False on error
            return
        
        await input.delete(True)
        file_name, ext = os.path.splitext(os.path.basename(x))
        credit = my_name

        path = f"./downloads/{m.chat.id}"

        try:
            with open(x, "r") as f:
                content = f.read()
            content = content.split("\n")
            links = []
            for i in content:
                links.append(i.split("://", 1))
            os.remove(x)
        except:
            await m.reply_text("Invalid file input.🥲")
            os.remove(x)
            bot_running = False  # Set bot_running to False for invalid file input
            return
    else:
        content = input.text
        content = content.split("\n")
        links = []
        for i in content:
            links.append(i.split("://", 1))

    #===================== IF ELSE ========================

    await editable.edit(f"🔍 **Do you want to set all values as Default?\nIf YES then type `df` 𝗢𝗧𝗛𝗘𝗥𝗪𝗜𝗦𝗘 `no`** ✨")
    input5: Message = await bot.listen(chat_id)
    raw_text5 = input5.text
    await input5.delete(True)


#===============================================================
    if raw_text5 == "df":
        await editable.edit("**📝 Enter the 𝗕𝗔𝗧𝗖𝗛 𝗡𝗔𝗠𝗘 or type `df` to use the text filename:**")
        input1 = await bot.listen(chat_id)
        raw_text0 = input1.text
        await input1.delete(True)
        if raw_text0 == 'df':
            try:
                b_name = file_name.replace('_', ' ')
            except Exception as e:
                print(f"Error: {e}")
                b_name = "I Don't Know"
        else:
            b_name = raw_text0
            
        raw_text = "1"
        raw_text2 = "720"
        res = "1280x720"
        CR = '<a href="https://t.me/ALTAFPATHAN">𝗣𝗔𝗧𝗛𝗔𝗡❤❤️</a>'
        raw_text4 = "df"
        thumb = "no"
      
        await editable.delete()  # Ensure the prompt message is deleted
    else:


    #===================== Batch Name =====================

        await editable.edit(f"Total links found are **{len(links)}**\n\nSend From where you want to download 𝗜𝗡𝗜𝗧𝗜𝗔𝗟 is **1**")
        input0: Message = await bot.listen(chat_id)
        raw_text = input0.text.strip()
        await input0.delete(True)

        await editable.edit("**Enter 𝗕𝗔𝗧𝗖𝗛 𝗡𝗔𝗠𝗘 or send df for grabbing it from text filename.**")
        input1: Message = await bot.listen(editable.chat.id)
        raw_text0 = input1.text
        await input1.delete(True)
        if raw_text0 == 'df':
            try:
                b_name = file_name
            except Exception as e:
                print(f"Error: {e}")
                b_name = "I Don't Know"
        else:
            b_name = raw_text0

    #===================== Title Name =====================

        await editable.edit(f"🔍 **Do you want to enable the 𝗧𝗜𝗧𝗟𝗘 Feature? Reply with `YES` or `df`** ✨")
        input4: Message = await bot.listen(chat_id)
        raw_text4 = input4.text
        await input4.delete(True)

    #===================== QUALITY =================================
        await editable.edit("**Enter resolution:**\n\n144\n240\n360\n480\n720\n1080\n1440\n2160\n4320\n\n**Please Choose 𝗤𝗨𝗔𝗟𝗜𝗧𝗜𝗬**\n\nor Send `df` for default Quality\n\n")
        input2: Message = await bot.listen(chat_id)
        if input2.text.lower() == "df": # Check if the input is "df" (case-insensitive)
            raw_text2 = "720"
        else:
            raw_text2 = input2.text
        await input2.delete(True)
        try:
            if raw_text2 == "144":
                res = "1280x720"
            elif raw_text2 == "240":
                res = "426x240"
            elif raw_text2 == "360":
                res = "640x360"
            elif raw_text2 == "480":
                res = "854x480"
            elif raw_text2 == "720":
                res = "1280x720"
            elif raw_text2 == "1080":
                res = "1920x1080" 
            elif raw_text2 == "1440":
                res = "2560x1440"
            elif raw_text2 == "2160":
                res = "3840x2160"
            elif raw_text2 == "4320":
                res = "7680x4320"
            else: 
                res = "854x480"
        except Exception:
            res = "UN"
        
        await editable.edit("**Enter 𝗬𝗢𝗨𝗥 𝗡𝗔𝗠𝗘 or send `df` to use default. 📝**")
        input3: Message = await bot.listen(chat_id)
        raw_text3 = input3.text
        await input3.delete(True)
        if raw_text3 == 'df':
            CR = '<a href="@Savebypathanloginbot">𝗣𝗔𝗧𝗛𝗔𝗡❤️</a>'
        else:
            CR = raw_text3    
        # Asking for thumbnail
        await editable.edit("Now upload the **𝗧𝗛𝗨𝗠𝗕𝗡𝗔𝗜𝗟 𝗜𝗠𝗔𝗚𝗘** or send `no` or `df` for default thumbnail 🖼️")
        input6 = await bot.listen(chat_id)

        if input6.photo:
            thumb = await input6.download()
        else:
            raw_text6 = input6.text
            if raw_text6 == "df":
                thumb = "thumbnail.jpg"
            elif raw_text6.startswith("http://") or raw_text6.startswith("https://"):
                getstatusoutput(f"wget '{raw_text6}' -O 'raw_text6.jpg'")
                thumb = "raw_text6.jpg"
            else:
                thumb = "no"
        await input6.delete(True)
        await editable.delete()
    
    # Initialize count and end_count
    count = 1
    end_count = None

    # Determine the range or starting point
    if '-' in raw_text:
        try:
            start, end = map(int, raw_text.split('-'))
            if start < 1 or end > len(links) or start >= end:
                await editable.edit("Invalid range. Please provide a valid range within the available links.")
                bot_running = False
                return
            count = start
            end_count = end
        except ValueError:
            await editable.edit("Invalid input format. Please provide a valid range (e.g., 1-50) or a starting point (e.g., 5).")
            bot_running = False
            return
    else:
        try:
            count = int(raw_text)
            if count < 1 or count > len(links):
                await editable.edit("Invalid start point. Please provide a valid start point within the available links.")
                bot_running = False
                return
            end_count = len(links)
        except ValueError:
            await editable.edit("Invalid input format. Please provide a valid range (e.g., 1-50) or a starting point (e.g., 5).")
            bot_running = False
            return

    try:
        await process_file(bot, m, links, b_name, count, end_count, raw_text2, res, CR, raw_text4, thumb, log_channel_id, my_name, overlay, accept_logs, collection)
    
    except Exception as e:
        await m.reply_text(e)

# Function to process a file
async def process_file(bot, m, links, b_name, count, end_count, raw_text2, res, CR, raw_text4, thumb, log_channel_id, my_name, overlay, accept_logs, collection):
    global bot_running
    global file_queue

    try:
        await bot.send_message(
            -1002155787742, 
            f"**•File name** - `{b_name}`\n**•Total Links Found In TXT** - `{len(links)}`\n**•RANGE** - `({count}-{end_count})`\n**•Resolution** - `{res}({raw_text2})`\n**•Caption** - **{CR}**\n**•Thumbnail** - **{thumb}**"
        )
        
        # Check if the bot is already running
        if bot_running:
            file_queue_data = {
                'm': m,
                'b_name': b_name,
                'links': links,
                'count': count,
                'end_count': end_count,
                'res': res,
                'raw_text2': raw_text2,
                'CR': CR,
                'raw_text4': raw_text4,
                'thumb': thumb,
                'log_channel_id': -1002155787742,
                'my_name': my_name,
                'overlay': overlay,
                'accept_logs': accept_logs
            }
            file_queue.append(file_queue_data)  # Add file data to queue
            save_queue_file(collection, file_queue)
            await m.reply_text("Bot is currently running. Your file is queued for processing.")
        
        else:
            bot_running = True
            await process_links(bot, m, links, b_name, count, end_count, raw_text2, res, CR, raw_text4, thumb, log_channel_id, my_name, overlay, accept_logs)
            await handle_queue(bot, m, collection)

    except Exception as e:
        msg = await m.reply_text("⚙️ Process will automatically start after completing the current one.")
        await asyncio.sleep(10)  # Wait for 10 seconds
        await msg.delete()  # Delete the message

async def handle_queue(bot, m, collection):
    global bot_running
    global file_queue

    while file_queue:
        file_data = file_queue.pop(0)
        try:
            await process_links(bot, file_data['m'], file_data['links'], file_data['b_name'], file_data['count'], file_data['end_count'], file_data['raw_text2'], file_data['res'], file_data['CR'], file_data['raw_text4'], file_data['thumb'], file_data['log_channel_id'], file_data['my_name'], file_data['overlay'], file_data['accept_logs'])
        except Exception as e:
            await m.reply_text(str(e))
    
    # Reset bot running status after all queued processes are completed
    bot_running = False

async def process_links(bot, m, links, b_name, count, end_count, raw_text2, res, CR, raw_text4, thumb, log_channel_id, my_name, overlay, accept_logs):
    # Your logic for processing links goes here
    global start_time, total_running_time, max_running_time

    total_running_time = load_bot_running_time(collection)
    max_running_time = load_max_running_time(collection)
    # Handle the case where only one link or starting from the first link
    if count == 1:
        chat_id = m.chat.id
        #========================= PINNING THE BATCH NAME ======================================
        batch_message: Message = await bot.send_message(chat_id, f"**{b_name}**")
        
        try:
            await bot.pin_chat_message(chat_id, batch_message.id)
            message_link = batch_message.link
        except Exception as e:
            await bot.send_message(chat_id, f"Failed to pin message: {str(e)}")
            message_link = None  # Fallback value

        message_id = batch_message.id 
        pinning_message_id = message_id + 1
        
        if message_link:
            end_message = (
                f"⋅ ─ list index (**{count}**-**{end_count}**) out of range ─ ⋅\n\n"
                f"✨ **BATCH** » <a href=\"{message_link}\">{b_name}</a> ✨\n\n"
                f"⋅ ─ DOWNLOADING ✩ COMPLETED ─ ⋅"
            )
        else:
            end_message = (
                f"⋅ ─ list index (**{count}**-**{end_count}**) out of range ─ ⋅\n\n"
                f"✨ **BATCH** » {b_name} ✨\n\n"
                f"⋅ ─ DOWNLOADING ✩ COMPLETED ─ ⋅"
            )

        try:
            await bot.delete_messages(chat_id, pinning_message_id)
        except Exception as e:
            await bot.send_message(chat_id, f"Failed to delete pinning message: {str(e)}")
    else:
        end_message = (
            f"⋅ ─ list index (**{count}**-**{end_count}**) out of range ─ ⋅\n\n"
            f"✨ **BATCH** » {b_name} ✨\n\n"
            f"⋅ ─ DOWNLOADING ✩ COMPLETED ─ ⋅"
        )

    for i in range(count - 1, end_count):
        if total_running_time >= max_running_time:
            await m.reply_text(f"⏳ You have used your {max_running_time / 3600:.2f} hours of bot running time. Please contact the owner to reset it.")
            return

        start_time = time.time()

        if len(links[i]) != 2 or not links[i][1]:
            # If the link is empty or not properly formatted, continue to the next iteration
            name1 = links[i][0].replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()
            name = f'{str(count).zfill(3)}) {name1[:60]} - {my_name}'
            await m.reply_text(f"No link found for **{name}**.")
            continue
        try:
            V = links[i][1].replace("file/d/","uc?export=download&id=").replace("www.youtube-nocookie.com/embed", "youtu.be").replace("?modestbranding=1", "").replace("/view?usp=sharing","") # .replace("mpd","m3u8")
            url = "https://" + V

            if "visionias" in url:
                async with ClientSession() as session:
                    async with session.get(url, headers={'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9', 'Accept-Language': 'en-US,en;q=0.9', 'Cache-Control': 'no-cache', 'Connection': 'keep-alive', 'Pragma': 'no-cache', 'Referer': 'http://www.visionias.in/', 'Sec-Fetch-Dest': 'iframe', 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Site': 'cross-site', 'Upgrade-Insecure-Requests': '1', 'User-Agent': 'Mozilla/5.0 (Linux; Android 12; RMX2121) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Mobile Safari/537.36', 'sec-ch-ua': '"Chromium";v="107", "Not=A?Brand";v="24"', 'sec-ch-ua-mobile': '?1', 'sec-ch-ua-platform': '"Android"',}) as resp:
                        text = await resp.text()
                        url = re.search(r"(https://.*?playlist.m3u8.*?)\"", text).group(1)

            elif 'media-cdn.classplusapp.com' in url:
                headers = {'Host': 'api.classplusapp.com', 'x-access-token': 'eyJhbGciOiJIUzM4NCIsInR5cCI6IkpXVCJ9.eyJpZCI6NDcwOTYwODIsIm9yZ0lkIjozNTExODAsInR5cGUiOjEsIm1vYmlsZSI6IjkxODAwNDQ1ODkwNCIsIm5hbWUiOiJzdWppdCB0aXdhcmkiLCJlbWFpbCI6InN1aml0dGl3YXJpMjIxMzA4QGdtYWlsLmM5bSIsImlzSW50ZXJuYXRpb25hbCI6MCwiZGVmYXVsdExhbmd1YWdlIjoiRU4iLCJjb3VudHJ5Q29kZSI6IklOIiwiY291bnRyeUlTTyI6IjkxIiwidGltZXpvbmUiOiJHTVQrNTozMCIsImlzRGl5Ijp0cnVlLCJvcmdDb2RlIjoiYnZqaGkiLCJpc0RpeVN1YmFkbWluIjowLCJmaW5nZXJwcmludElkIjoiMmIzMDFjMzRiODkxZmJhMmE1Y2YyYjYyNDA3NjVhNDIiLCJpYXQiOjE3MjQzMzEwNzcsImV4cCI6MTcyNDkzNTg3N30.0oi58SRgPcKtA-vSoYFBiBh2_dIsGnFnlTak1oaxXZZtAzpEo1omoE5zoc4cim9U', 'user-agent': 'Mobile-Android', 'app-version': '1.4.37.1', 'api-version': '18', 'device-id': '5d0d17ac8b3c9f51', 'device-details': '2848b866799971ca_2848b8667a33216c_SDK-30', 'accept-encoding': 'gzip'}
                params = (('url', f'{url}'),)
                response = requests.get('https://api.classplusapp.com/cams/uploader/video/jw-signed-url', headers=headers, params=params)
                url = response.json()['url']	
                
            
            elif "tencdn.classplusapp" in url:
                headers = {'Host': 'api.classplusapp.com', 'x-access-token': 'eyJhbGciOiJIUzM4NCIsInR5cCI6IkpXVCJ9.eyJpZCI6NDcwOTYwODIsIm9yZ0lkIjozNTExODAsInR5cGUiOjEsIm1vYmlsZSI6IjkxODAwNDQ1ODkwNCIsIm5hbWUiOiJzdWppdCB0aXdhcmkiLCJlbWFpbCI6InN1aml0dGl3YXJpMjIxMzA4QGdtYWlsLmM5bSIsImlzSW50ZXJuYXRpb25hbCI6MCwiZGVmYXVsdExhbmd1YWdlIjoiRU4iLCJjb3VudHJ5Q29kZSI6IklOIiwiY291bnRyeUlTTyI6IjkxIiwidGltZXpvbmUiOiJHTVQrNTozMCIsImlzRGl5Ijp0cnVlLCJvcmdDb2RlIjoiYnZqaGkiLCJpc0RpeVN1YmFkbWluIjowLCJmaW5nZXJwcmludElkIjoiMmIzMDFjMzRiODkxZmJhMmE1Y2YyYjYyNDA3NjVhNDIiLCJpYXQiOjE3MjQzMzEwNzcsImV4cCI6MTcyNDkzNTg3N30.0oi58SRgPcKtA-vSoYFBiBh2_dIsGnFnlTak1oaxXZZtAzpEo1omoE5zoc4cim9U', 'user-agent': 'Mobile-Android', 'app-version': '1.4.37.1', 'api-version': '18', 'device-id': '5d0d17ac8b3c9f51', 'device-details': '2848b866799971ca_2848b8667a33216c_SDK-30', 'accept-encoding': 'gzip'}
                params = (('url', f'{url}'),)
                response = requests.get('https://api.classplusapp.com/cams/uploader/video/jw-signed-url', headers=headers, params=params)
                url = response.json()['url']	

            elif 'videos.classplusapp.com' in url:
                headers = {'Host': 'api.classplusapp.com', 'x-access-token': 'eyJhbGciOiJIUzM4NCIsInR5cCI6IkpXVCJ9.eyJpZCI6NDcwOTYwODIsIm9yZ0lkIjozNTExODAsInR5cGUiOjEsIm1vYmlsZSI6IjkxODAwNDQ1ODkwNCIsIm5hbWUiOiJzdWppdCB0aXdhcmkiLCJlbWFpbCI6InN1aml0dGl3YXJpMjIxMzA4QGdtYWlsLmM5bSIsImlzSW50ZXJuYXRpb25hbCI6MCwiZGVmYXVsdExhbmd1YWdlIjoiRU4iLCJjb3VudHJ5Q29kZSI6IklOIiwiY291bnRyeUlTTyI6IjkxIiwidGltZXpvbmUiOiJHTVQrNTozMCIsImlzRGl5Ijp0cnVlLCJvcmdDb2RlIjoiYnZqaGkiLCJpc0RpeVN1YmFkbWluIjowLCJmaW5nZXJwcmludElkIjoiMmIzMDFjMzRiODkxZmJhMmE1Y2YyYjYyNDA3NjVhNDIiLCJpYXQiOjE3MjQzMzEwNzcsImV4cCI6MTcyNDkzNTg3N30.0oi58SRgPcKtA-vSoYFBiBh2_dIsGnFnlTak1oaxXZZtAzpEo1omoE5zoc4cim9U', 'user-agent': 'Mobile-Android', 'app-version': '1.4.37.1', 'api-version': '18', 'device-id': '5d0d17ac8b3c9f51', 'device-details': '2848b866799971ca_2848b8667a33216c_SDK-30', 'accept-encoding': 'gzip'}
                params = (('url', f'{url}'),)
                response = requests.get('https://api.classplusapp.com/cams/uploader/video/jw-signed-url', headers=headers, params=params)
                url = response.json()['url']
              
            elif "edge.api.brightcove.com" in url:
                bcov = 'bcov_auth=eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE3MjQyMzg3OTEsImNvbiI6eyJpc0FkbWluIjpmYWxzZSwiYXVzZXIiOiJVMFZ6TkdGU2NuQlZjR3h5TkZwV09FYzBURGxOZHowOSIsImlkIjoiZEUxbmNuZFBNblJqVEROVmFWTlFWbXhRTkhoS2R6MDkiLCJmaXJzdF9uYW1lIjoiYVcxV05ITjVSemR6Vm10ak1WUlBSRkF5ZVNzM1VUMDkiLCJlbWFpbCI6Ik5Ga3hNVWhxUXpRNFJ6VlhiR0ppWTJoUk0wMVdNR0pVTlU5clJXSkRWbXRMTTBSU2FHRnhURTFTUlQwPSIsInBob25lIjoiVUhVMFZrOWFTbmQ1ZVcwd1pqUTViRzVSYVc5aGR6MDkiLCJhdmF0YXIiOiJLM1ZzY1M4elMwcDBRbmxrYms4M1JEbHZla05pVVQwOSIsInJlZmVycmFsX2NvZGUiOiJOalZFYzBkM1IyNTBSM3B3VUZWbVRtbHFRVXAwVVQwOSIsImRldmljZV90eXBlIjoiYW5kcm9pZCIsImRldmljZV92ZXJzaW9uIjoiUShBbmRyb2lkIDEwLjApIiwiZGV2aWNlX21vZGVsIjoiU2Ftc3VuZyBTTS1TOTE4QiIsInJlbW90ZV9hZGRyIjoiNTQuMjI2LjI1NS4xNjMsIDU0LjIyNi4yNTUuMTYzIn19.snDdd-PbaoC42OUhn5SJaEGxq0VzfdzO49WTmYgTx8ra_Lz66GySZykpd2SxIZCnrKR6-R10F5sUSrKATv1CDk9ruj_ltCjEkcRq8mAqAytDcEBp72-W0Z7DtGi8LdnY7Vd9Kpaf499P-y3-godolS_7ixClcYOnWxe2nSVD5C9c5HkyisrHTvf6NFAuQC_FD3TzByldbPVKK0ag1UnHRavX8MtttjshnRhv5gJs5DQWj4Ir_dkMcJ4JaVZO3z8j0OxVLjnmuaRBujT-1pavsr1CCzjTbAcBvdjUfvzEhObWfA1-Vl5Y4bUgRHhl1U-0hne4-5fF0aouyu71Y6W0eg'
                url = url.split("bcov_auth")[0]+bcov
        

            elif "master.mpd" in url:
                vid_id = url.split('/')[-2]
                url = f"https://pw.jarviss.workers.dev?v={vid_id}&quality={raw_text2}"

            name1 = links[i][0].replace("\t", "").replace(":", "").replace("/", "").replace("+", "").replace("#", "").replace("|", "").replace("@", "").replace("*", "").replace(".", "").replace("https", "").replace("http", "").strip()
            name = f'{str(count).zfill(3)}) {name1[:60]} - {my_name}'

            if "embed" in url:
                ytf = f"bestvideo[height<={raw_text2}]+bestaudio/best[height<={raw_text2}]"
            elif "youtube" in url:
                ytf = f"bestvideo[height<={raw_text2}][ext=mp4]+bestaudio[ext=m4a]/best[height<={raw_text2}][ext=mp4]"
            else:
                ytf = f"b[height<={raw_text2}]/bv[height<={raw_text2}]+ba/b/bv+ba"


            #if "jw-prod" in url and (url.endswith(".mp4") or "Expires=" in url):
                #cmd = f'yt-dlp -o "{name}.mp4" "{url}"'

            if "jw-prod" in url and (url.endswith(".mp4") or "Expires=" in url):
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"             
                cmd = f'yt-dlp -o "{name}.mp4" --user-agent "{user_agent}" "{url}"'

            else:
                cmd = f'yt-dlp -f "{ytf}" "{url}" -o "{name}.mp4"'

#===============================================================
            if raw_text4 == "YES":
                # Check the format of the link to extract video name and topic name accordingly
                if links[i][0].startswith("("):
                    # Extract the topic name for format: (TOPIC) Video Name:URL
                    t_name = re.search(r"\((.*?)\)", links[i][0]).group(1).strip().upper()
                    v_name = re.search(r"\)\s*(.*?):", links[i][0]).group(1).strip()
                else:
                    # Extract the topic name for format: Video Name (TOPIC):URL
                    t_name = re.search(r"\((.*?)\)", links[i][0]).group(1).strip().upper()
                    v_name = links[i][0].split("(", 1)[0].strip()

                name = f'{str(count).zfill(3)}) {name1[:60]} - {my_name}'

                cc = f'⋅ ─  **{t_name}**  ─ ⋅\n\n[🎬] **Video_ID** : {str(count).zfill(3)}.\n**𝑽𝒊𝒅𝒆𝒐 𝑵𝒂𝒎𝒆** : **{v_name}** ({res}) - {my_name}.mkv\n\n**𝑩𝒂𝒕𝒄𝒉 𝑵𝒂𝒎𝒆**: `{b_name}`\n\n**𝑫𝒐𝒘𝒏𝒍𝒐𝒂𝒅𝒆𝒅 𝑩𝒚 : {CR}**'
                cc1 = f'⋅ ─  **{t_name}**  ─ ⋅\n\n[📁] **File ID** : {str(count).zfill(3)}.\n**𝑭𝒊𝒍𝒆 𝑵𝒂𝒎𝒆** : **{v_name}** - {my_name}.pdf\n\n**𝑩𝒂𝒕𝒄𝒉 𝑵𝒂𝒎𝒆** : `{b_name}`\n\n**𝑫𝒐𝒘𝒏𝒍𝒐𝒂𝒅𝒆𝒅 𝑩𝒚 : {CR}**'

            else:
                cc = f'**[📹] Video_ID : {str(count).zfill(3)}.**\n\n**𝑽𝒊𝒅𝒆𝒐 𝑵𝒂𝒎𝒆** : **{name1}** - ({res}) {my_name}.mkv\n\n**𝑩𝒂𝒕𝒄𝒉 𝑵𝒂𝒎𝒆** : `{b_name}`\n\n**𝑫𝒐𝒘𝒏𝒍𝒐𝒂𝒅𝒆𝒅 𝑩𝒚 : {CR}**'
                cc1 = f'**[📁] File_ID : {str(count).zfill(3)}.**\n\n**𝑭𝒊𝒍𝒆 𝑵𝒂𝒎𝒆** : **{name1}** - {my_name}.pdf\n\n**𝑩𝒂𝒕𝒄𝒉 𝑵𝒂𝒎𝒆** : `{b_name}`\n\n**𝑫𝒐𝒘𝒏𝒍𝒐𝒂𝒅𝒆𝒅 𝑩𝒚 : {CR}**'                             
                
            if "drive" in url:
                try:
                    ka = await helper.download(url, name)
                    message = await bot.send_document(chat_id=m.chat.id,document=ka, caption=cc1)
                    if accept_logs == 1:  
                        file_id = message.document.file_id
                        await bot.send_document(chat_id=-1002155787742, document=file_id, caption=cc1)
                    count+=1
                    os.remove(ka)
                    time.sleep(1)
                except FloodWait as e:
                    await m.reply_text(str(e))
                    time.sleep(e.x)
                    continue
            elif ".pdf" in url:
                try:
                    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'}
                    if "encrypted" in url:
                        # Handle encrypted PDF URLs differently if needed
                        async with aiohttp.ClientSession(headers=headers) as session:
                            async with session.get(url) as response:
                                if response.status == 200:
                                    pdf_data = await response.read()
                                    with open(f"{name}.pdf", 'wb') as f:
                                        f.write(pdf_data)
                                    message = await bot.send_document(chat_id=m.chat.id, document=f'{name}.pdf', caption=cc1)
                                    if accept_logs == 1:
                                        file_id = message.document.file_id
                                        await bot.send_document(chat_id=-1002155787742, document=file_id, caption=cc1)
                                    count += 1
                                    os.remove(f'{name}.pdf')
                                else:
                                    await m.reply_text(f"Failed to download PDF. Status code: {response.status}")
                    else:
                        cmd = f'yt-dlp -o "{name}.pdf" "{url}"'
                        download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                        os.system(download_cmd)
                        
                        if os.path.exists(f'{name}.pdf'):
                            new_name = f'{my_name}-{name}.pdf'
                            os.rename(f'{name}.pdf', new_name)
                            message = await bot.send_document(chat_id=m.chat.id, document=new_name, caption=cc1)
                            if accept_logs == 1:
                                file_id = message.document.file_id
                                await bot.send_document(chat_id=-1002155787742, document=file_id, caption=cc1)
                            count += 1
                            os.remove(new_name)
                        else:
                            async with aiohttp.ClientSession(headers=headers) as session:
                                async with session.get(url) as response:
                                    if response.status == 200:
                                        pdf_data = await response.read()
                                        with open(f"{name}.pdf", 'wb') as f:
                                            f.write(pdf_data)
                                        message = await bot.send_document(chat_id=m.chat.id, document=f'{name}.pdf', caption=cc1)
                                        if accept_logs == 1:
                                            file_id = message.document.file_id
                                            await bot.send_document(chat_id=-1002155787742, document=file_id, caption=cc1)
                                        count += 1
                                        os.remove(f'{name}.pdf')
                                    else:
                                        await m.reply_text(f"Failed to download PDF. Status code: {response.status}")
                except Exception as e:
                    await m.reply_text(f"Error: {str(e)}")
                    time.sleep(e.x)
                    continue
            elif any(ext in url for ext in [".mp3", ".wav", ".m4a"]):
                try:
                    ext = url.split('.')[-1]
                    cmd = f'yt-dlp -x --audio-format {ext} -o "{name}.{ext}" "{url}"'
                    download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                    os.system(download_cmd)
                    cc2 = f'**[🎵] Audio_ID : {str(count).zfill(3)}.**\n\n**𝑭𝒊𝒍𝒆 𝑵𝒂𝒎𝒆** : **{name1}** {my_name}.{ext}\n\n**𝑩𝒂𝒕𝒄𝒉 𝑵𝒂𝒎𝒆** : `{b_name}`\n\n**𝑫𝒐𝒘𝒏𝒍𝒐𝒂𝒅𝒆𝒅 𝑩𝒚 : {CR}**'
                    await bot.send_document(chat_id=m.chat.id, document=f'{name}.{ext}', caption=cc2)
                    #if accept_logs == 1:  
                        #file_id = message.document.file_id
                        #await bot.send_document(chat_id=-1002155787742, document=file_id, caption=cc2)
                    count += 1
                    os.remove(f'{name}.{ext}')
                except FloodWait as e:
                    await m.reply_text(str(e))
                    time.sleep(e.x)
                    continue
            elif any(ext in url for ext in [".jpg", ".jpeg", ".png"]):
                try:
                    ext = url.split('.')[-1]
                    cmd = f'yt-dlp -o "{name}.{ext}" "{url}"'
                    download_cmd = f"{cmd} -R 25 --fragment-retries 25"
                    os.system(download_cmd)
                    cc3 = f'**[🖼️] Image_ID : {str(count).zfill(3)}.**\n\n**𝑭𝒊𝒍𝒆 𝑵𝒂𝒎𝒆** : **{name1}** {my_name}.{ext}\n\n**𝑩𝒂𝒕𝒄𝒉 𝑵𝒂𝒎𝒆** : `{b_name}`\n\n**𝑫𝒐𝒘𝒏𝒍𝒐𝒂𝒅𝒆𝒅 𝑩𝒚 : {CR}**'
                    message = await bot.send_document(chat_id=m.chat.id, document=f'{name}.{ext}', caption=cc3)
                    if accept_logs == 1:  
                        file_id = message.document.file_id
                        await bot.send_document(chat_id=-1002155787742, document=file_id, caption=cc3)
                    count += 1
                    os.remove(f'{name}.{ext}')
                except FloodWait as e:
                    await m.reply_text(str(e))
                    time.sleep(e.x)
                    continue
            else:
                if 'penpencil' in url:
                    prog = await m.reply_text(
                        f"**🚧 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐈𝐍𝐆 🚧**\n\n"
                        f"**🎬 Name » ** `{name}`\n"
                        f"**🔍 Quality » ** `{raw_text2}`\n\n"
                        f"**Processing Physics Wallah (PW) videos may take some time. ⏳**\n\n"
                        f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
                    )
                elif 'visionias' in url:
                    prog = await m.reply_text(
                        f"**🚧 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐈𝐍𝐆 🚧**\n\n"
                        f"**🎬 Name » ** `{name}`\n"
                        f"**🔍 Quality » ** `{raw_text2}`\n\n"
                        f"**Downlaoding Vision IAS videos may take some time. ⏳**\n\n"
                        f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
                    )
                elif 'brightcove' in url:
                    prog = await m.reply_text(
                        f"**🚧 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐈𝐍𝐆 🚧**\n\n"
                        f"**🎬 Name » ** `{name}`\n"
                        f"**🔍 Quality » ** `{raw_text2}`\n\n"
                        f"**Downlaoding Careerwill (CW) videos may take some time. ⏳**\n\n"
                        f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
                    )
                elif 'utkarshapp' in url:
                    prog = await m.reply_text(
                        f"**🚧 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐈𝐍𝐆 🚧**\n\n"
                        f"**🎬 Name » ** `{name}`\n"
                        f"**🔍 Quality » ** `{raw_text2}`\n\n"
                        f"**Downlaoding Utkarsh videos may take some time. ⏳**\n\n"
                        f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
                    )
                elif 'studyiq' in url:
                    prog = await m.reply_text(
                        f"**🚧 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐈𝐍𝐆 🚧**\n\n"
                        f"**🎬 Name » ** `{name}`\n"
                        f"**🔍 Quality » ** `{raw_text2}`\n\n"
                        f"**Downlaoding StudyIQ videos may take some time. ⏳**\n\n"
                        f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
                    )
                else:
                    prog = await m.reply_text(
                        f"**🚧 𝐃𝐎𝐖𝐍𝐋𝐎𝐀𝐃𝐈𝐍𝐆 🚧**\n\n"
                        f"**🎬 Name » ** `{name}`\n"
                        f"**🔍 Quality » ** `{raw_text2}`\n"
                        f"**🌐 Video Link » ** `{url}`\n\n"
                        f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
                    )
                res_file = await helper.download_video(url, cmd, name)
                filename = res_file
                await prog.delete(True)
                if overlay is not None: 
                    await helper.send_video_watermark(bot, m, url, cc, filename, thumb, name, overlay)
                else:
                    if accept_logs == 1:
                        await helper.send_vid(bot, m, url, cc, filename, thumb, name, -1002155787742) 
                    else:
                        await helper.send_video_normal(bot, m, url, cc, filename, thumb, name)
                count += 1

            elapsed_time = time.time() - start_time
            total_running_time = save_bot_running_time(collection, elapsed_time)
            start_time = None
            
        except Exception as e:
            logging.error(e)
            if "pw.jarviss.workers" in url and "mpd" in url:
                await m.reply_text(
                f"**❌ Download Failed! (PW DRM) ❌**\n\n"
                f"**🎬 Name » ** `{name}`\n"
                f"**🔍 Quality » ** `{raw_text2}`\n"
                f"**🌐 URL » ** `{url}`\n\n"
                f"Please check the URL and try again. 🔄\n\n"
                f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
            )
            elif "cpvod" in url:
                await m.reply_text(
                f"**❌ Download Failed! (CPVOD DRM) ❌**\n\n"
                f"**🎬 Name » ** `{name}`\n"
                f"**🔍 Quality » ** `{raw_text2}`\n"
                f"**🌐 URL » ** `{url}`\n\n"
                f"Please check the URL and try again. 🔄\n\n"
                f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
            )
            elif "vdocipher" in url:
                await m.reply_text(
                f"**❌ Download Failed! (VDOCIPHER DRM) ❌**\n\n"
                f"**🎬 Name » ** `{name}`\n"
                f"**🔍 Quality » ** `{raw_text2}`\n"
                f"**🌐 URL » ** `{url}`\n\n"
                f"Please check the URL and try again. 🔄\n\n"
                f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
            )
            elif "vimeo" in url:
                await m.reply_text(
                f"**❌ Download Failed! (VIMEO DRM) ❌**\n\n"
                f"**🎬 Name » ** `{name}`\n"
                f"**🔍 Quality » ** `{raw_text2}`\n"
                f"**🌐 URL » ** `{url}`\n\n"
                f"Please check the URL and try again. 🔄\n\n"
                f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
            )
            else:
                await m.reply_text(
                f"**❌ Download Failed! ❌**\n\n"
                f"**🎬 Name » ** `{name}`\n"
                f"**🔍 Quality » ** `{raw_text2}`\n"
                f"**🌐 URL » ** `{url}`\n\n"
                f"Please check the URL and try again. 🔄\n\n"
                f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
            )
            time.sleep(3)
            count += 1
            continue

    bot_running = False
    start_time = None
    await m.reply_text(f"{end_message}")
    if accept_logs == 1:
        await bot.send_message(-1002155787742, f"{end_message}")
    await m.reply_text("That's it ❤️")


#===================== TEXT MESSAGES THAT BOT WILL SEND ===============

help_text = """

🤖 **Welcome to Bot Commands and Usage Guide!**

🔑 **Allowed Channels Commands:**

1. **/show_channels** - 📺 Display the list of allowed channels.

2. **/add_channel `<-100channelid>`** - ➕ Add a channel to the allowed channels list.

 **Example:**
 ```
 /add_channel -100973847334
 ```
OR Use /add_chat 

3. **/remove_channel `<-100channelid>`** - ➖ Remove a channel from the allowed channels list.

 **Example:**
 ```
 /remove_channel -1003947384
 ```
OR Use /remove_chat

🚀 **General Commands:**

4. **/pathan** - 💡 Type this before sending your **📃.txt** file.

5. **/start** - 📛 Start the bot and receive a welcome message.

6. **/stop** - 🛑 Stop the bot.

🌟 **Bot Running Time:**

7. **/bot_running_time** - ⏲️ Check the total running time of your bot.

🪓 **Txt Extractor and Editor Commands:**

8. **/youtube** - 🎥 Convert a YouTube URL to a .txt file.

9. **/remtitle** - ✂️ Remove extra parentheses from the .txt file.

10. **/h2t** - 🔄 Convert your .html file to a .txt file.

11. **/studyiqeditor** - 📝 Convert your studyiq file.

💊 **Powerful Pill**

12. **/restart** - ▶️ Continue the process from the same point where it has been stopped.

📌 **Note:** Commands are restricted to the bot owner or authorized users only.

Feel free to contact @ALTAFPATHAN for further assistance or subscription details.

✨ Have fun and happy chatting! ✨

"""


OWNER_TEXT = """

🤖 **Welcome to Bot Commands and Usage Guide!**

📝 **Owner Commands:**

1. **/add_log_channel `<-100channelid>`** - 📁 Set the log channel ID.

**Example:**
```
/add_log_channel -10054567890
```

2. **/accept_logs** - 📥 Set this to **1** if you want the backup.

3. **/logs** - 📝 Send the logs from the last two minutes.

4. **/watermark** - 🌊 Add a custom watermark to your video.

5. **/name** - 🏷️ Set a custom name that you want to display before the file extension.

**Example:**
```
/name yourname
```

🔒 **Authorized Users Commands:**

6. **/auth_users** - 👥 Display the list of authorized users.

7. **/add_auth `<userID>`** - ➕ Add a user to the authorized users list.

**Example:**
```
/add_auth 3495890
```

8. **/remove_auth `<userID>`** - ➖ Remove a user from the authorized users list.

**Example:**
```
/remove_auth 3957994
```

🔑 **Allowed Channels Commands:**

9. **/show_channels** - 📺 Display the list of allowed channels.

10. **/add_channel `<-100channelid>`** - ➕ Add a channel to the allowed channels list.

 **Example:**
 ```
 /add_channel -100973847334
 ```

11. **/remove_channel `<-100channelid>`** - ➖ Remove a channel from the allowed channels list.

 **Example:**
 ```
 /remove_channel -1003947384
 ```

🚀 **General Commands:**

12. **/pathan** - 💡 Type this before sending your **📃.txt** file.

13. **/start** - 📛 Start the bot and receive a welcome message.

14. **/stop** - 🛑 Stop the bot.

🌟 **Bot Running Time:**

15. **/bot_running_time** - ⏲️ Check the total running time of your bot.

16. **/reset_bot_running_time `<hours>`** - 🔄 Reset bot running time to specific hours.

17. **/set_max_running_time `<hours>`** - ⏳ Set maximum bot running time.

⛏️ **Txt Extractor and Editor Commands:**

18. **/youtube** - 🎥 Convert a YouTube URL to a .txt file.

19. **/remtitle** - ✂️ Remove extra parentheses from the .txt file.

20. **/h2t** - 🔄 Convert your .html file to a .txt file.

21. **/studyiqeditor** - 📝 Convert your studyiq file.

💊 **Powerfull Pill**

22. **/restart** - ▶️ Continue the process from the same point where it has been stopped.

📌 **Note:** Commands are restricted to the bot owner or authorized users only.

Feel free to contact @ALTAFPATHAN for further assistance or subscription details.

✨ Have fun and happy chatting! ✨

"""


#============== Load initial data on startup =========================
load_initial_data()

#====================== Inline keyboard buttons =======================

#========== Button showed on start command ==========
help_button_keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("Help", callback_data="help"),
        ]
    ]
)


#========== Button showed on help command =============

# Inline keyboard
keyboard = InlineKeyboardMarkup(
    [
        [
            InlineKeyboardButton("Add Chat", callback_data="add_chat"),
            InlineKeyboardButton("Remove Chat", callback_data="remove_chat"),
            InlineKeyboardButton("Show Channels", callback_data="show_channels"),
        ]
    ]
)

#================== id command button ===========================

BUTTONS = InlineKeyboardMarkup([[InlineKeyboardButton(text="Send Here", url=f"https://t.me/ALTAFPATHAN")]])

bot.run()

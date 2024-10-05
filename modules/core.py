import os
import re
import sys
import json
import time
import datetime
import aiohttp
import aiofiles
import asyncio
import logging
import requests
import tgcrypto
import subprocess
import concurrent.futures
from subprocess import getstatusoutput
from pyrogram import Client, filters
from pyrogram.types import Message
from utils import progress_bar
import subprocess
from math import ceil
from PIL import Image
from pytube import Playlist  #Youtube Playlist Extractor
from yt_dlp import YoutubeDL


failed_counter = 0

def duration(filename):
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                             "format=duration", "-of",
                             "default=noprint_wrappers=1:nokey=1", filename],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT)
    return float(result.stdout)
    
def exec(cmd):
        process = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        output = process.stdout.decode()
        print(output)
        return output
        #err = process.stdout.decode()
def pull_run(work, cmds):
    with concurrent.futures.ThreadPoolExecutor(max_workers=work) as executor:
        print("**__Waiting for tasks to complete__**")
        fut = executor.map(exec,cmds)
async def aio(url,name):
    k = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(k, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return k


async def download(url,name):
    ka = f'{name}.pdf'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                f = await aiofiles.open(ka, mode='wb')
                await f.write(await resp.read())
                await f.close()
    return ka



def parse_vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = []
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",2)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    new_info.append((i[0], i[2]))
            except:
                pass
    return new_info


def vid_info(info):
    info = info.strip()
    info = info.split("\n")
    new_info = dict()
    temp = []
    for i in info:
        i = str(i)
        if "[" not in i and '---' not in i:
            while "  " in i:
                i = i.replace("  ", " ")
            i.strip()
            i = i.split("|")[0].split(" ",3)
            try:
                if "RESOLUTION" not in i[2] and i[2] not in temp and "audio" not in i[2]:
                    temp.append(i[2])
                    
                    # temp.update(f'{i[2]}')
                    # new_info.append((i[2], i[0]))
                    #  mp4,mkv etc ==== f"({i[1]})" 
                    
                    new_info.update({f'{i[2]}':f'{i[0]}'})

            except:
                pass
    return new_info



async def run(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE)

    stdout, stderr = await proc.communicate()

    print(f'[{cmd!r} exited with {proc.returncode}]')
    if proc.returncode == 1:
        return False
    if stdout:
        return f'[stdout]\n{stdout.decode()}'
    if stderr:
        return f'[stderr]\n{stderr.decode()}'

    

def old_download(url, file_name, chunk_size = 1024 * 10):
    if os.path.exists(file_name):
        os.remove(file_name)
    r = requests.get(url, allow_redirects=True, stream=True)
    with open(file_name, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            if chunk:
                fd.write(chunk)
    return file_name


def human_readable_size(size, decimal_places=2):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size < 1024.0 or unit == 'PB':
            break
        size /= 1024.0
    return f"{size:.{decimal_places}f} {unit}"


def time_name():
    date = datetime.date.today()
    now = datetime.datetime.now()
    current_time = now.strftime("%H%M%S")
    return f"{date} {current_time}.mp4"

#======================== YOUTUBE EXTRACTOR =====================

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
    with YoutubeDL(ydl_opts) as ydl:
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


#============================= Multiple retries ==================
async def download_video(url, cmd, name):
    download_cmd = f'{cmd} -R 25 --fragment-retries 25 --external-downloader aria2c --downloader-args "aria2c: -x 16 -j 32"'
    global failed_counter
    print(download_cmd)
    logging.info(download_cmd)
    k = subprocess.run(download_cmd, shell=True)
    
    # Check if the URL is of type 'visionias' or 'penpencilvod'
    if "visionias" in cmd:
        return await download_visionias(url, cmd, name)
    elif "penpencilvod" in cmd:
        return await download_penpencilvod(url, cmd, name)
    else:
        # Default handling for other types of URLs
        return await default_download(url, cmd, name)

async def download_visionias(url, cmd, name):
    global failed_counter
    # Retry logic for 'visionias' URLs
    if failed_counter <= 10:
        failed_counter += 1
        await asyncio.sleep(5)
        return await download_video(url, cmd, name)
    else:
        # Reset failed_counter if the download succeeds
        failed_counter = 0
        return await default_download(url, cmd, name)

async def download_penpencilvod(url, cmd, name):
    global failed_counter
    # Retry logic for 'penpencilvod' URLs
    if failed_counter <= 10:
        failed_counter += 1
        await asyncio.sleep(5)
        return await download_video(url, cmd, name)
    else:
        # Reset failed_counter if the download succeeds
        failed_counter = 0
        return await default_download(url, cmd, name)
    
async def default_download(url, cmd, name):
    # Default download logic
    try:
        if os.path.isfile(name):
            return name
        elif os.path.isfile(f"{name}.webm"):
            return f"{name}.webm"
        name = name.split(".")[0]
        if os.path.isfile(f"{name}.mkv"):
            return f"{name}.mkv"
        elif os.path.isfile(f"{name}.mp4"):
            return f"{name}.mp4"
        elif os.path.isfile(f"{name}.mp4.webm"):
            return f"{name}.mp4.webm"
        return name
    except FileNotFoundError as exc:
        return os.path.splitext(name)[0] + ".mp4"

#------------------Normal handler for the documents-------------------

async def send_doc(bot: Client, m: Message,cc,ka,cc1,count,name):
    reply = await m.reply_text(f"**Uploading ..🚀..** - `{name}`\n╰────⌈**𝗣𝗔𝗧𝗛𝗔𝗡❤️**⌋────╯")
    time.sleep(1)
    await m.reply_document(ka,caption=cc1)
    count+=1
    await reply.delete (True)
    time.sleep(1)
    os.remove(ka)
    time.sleep(3)

#-----------------Send it to the log channel-----------------------
async def send_doc(bot: Client, m: Message, cc, ka, cc1, count, name, log_channel_id):
    reply = await m.reply_text(f"**Uploading ..🚀..** - `{name}`\n╰────⌈**𝗣𝗔𝗧𝗛𝗔𝗡❤️**⌋────╯")
    time.sleep(1)
    # Upload the document and capture the message
    message = await m.reply_document(ka, caption=cc1)
    # Capture the file_id of the uploaded document
    file_id = message.document.file_id
    # Send the document to the log channel using file_id
    await bot.send_document(log_channel_id, file_id, caption=cc1)    
    # Increment count
    count += 1
    # Delete the reply message
    await reply.delete(True)
    # Remove the local file
    time.sleep(1)
    os.remove(ka)
    time.sleep(3)


def get_video_attributes(file: str):
    """Returns video duration, width, height"""

    class FFprobeAttributesError(Exception):
        """Exception if ffmpeg fails to generate attributes"""

    cmd = (
        "ffprobe -v error -show_entries format=duration "
        + "-of default=noprint_wrappers=1:nokey=1 "
        + "-select_streams v:0 -show_entries stream=width,height "
        + f" -of default=nw=1:nk=1 '{file}'"
    )
    res, out = getstatusoutput(cmd)
    if res != 0:
        raise FFprobeAttributesError(out)
    width, height, dur = out.split("\n")
    return (int(float(dur)), int(width), int(height))

#================= Spliting According to File Size ==================

def duration(filename):
    result = subprocess.run(f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{filename}"', 
                            shell=True, 
                            capture_output=True, 
                            text=True)
    return float(result.stdout.strip())

def duration(part):
    result = subprocess.run(f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{part}"', 
                            shell=True, 
                            capture_output=True, 
                            text=True)
    return float(result.stdout.strip())

def split_video(filename, max_size):
    parts = []
    part_prefix = filename.split('.')[0]  # Get the filename without extension

    # Calculate the total duration of the video
    total_duration = duration(filename)
    
    # Estimate the duration of each segment to be under the max_size
    file_size = os.path.getsize(filename)
    segment_duration = ceil((total_duration * max_size) / file_size)
    
    # Command to split the video, using MKV container
    split_command = f'ffmpeg -y -i "{filename}" -c copy -map 0 -segment_time {segment_duration} -f segment "{part_prefix}_part_%03d.mkv"'
    subprocess.run(split_command, shell=True)
    
    for part in os.listdir():
        if part.startswith(part_prefix) and part.endswith('.mkv'):
            parts.append(part)
    
    return parts


#-----------------------Emoji handler------------------------------------

EMOJIS = ["🦁", "🐶", "🐼", "🐱", "👻", "🐻‍❄️", "☁️", "🚹", "🚺", "🐠", "🦋"]
emoji_counter = 0  # Initialize a global counter

def get_next_emoji():
    global emoji_counter
    emoji = EMOJIS[emoji_counter]
    emoji_counter = (emoji_counter + 1) % len(EMOJIS)
    return emoji

async def send_video_normal(bot: Client, m: Message, url, cc, filename, thumb, name):
    emoji = get_next_emoji()
    subprocess.run(f'ffmpeg -y -i "{filename}" -ss 00:00:12 -vframes 1 "{filename}.jpg"', shell=True)
    if 'pw.jarviss.workers' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 𝐍𝐚𝐦𝐞 » ** `{name}`\n\n"
            f"**⏳Processing Physics Wallah (PW) videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'rgvikramjeet-data' in url and 'appx-transcoded' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 𝐍𝐚𝐦𝐞 » ** `{name}`\n\n"
            f"**⏳Uploading RG Vikramjeet videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'parmaracademy-data' in url and 'appx-transcoded' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 𝐍𝐚𝐦𝐞 » ** `{name}`\n\n"
            f"**⏳Uploading Parmar Academy videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'uclive-data' in url and 'appx-transcoded' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 𝐍𝐚𝐦𝐞 » ** `{name}`\n\n"
            f"**⏳Uploading UC Live videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'visionias' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 𝐍𝐚𝐦𝐞 » ** `{name}`\n\n"
            f"**⏳Uploading Vision IAS videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'brightcove' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 𝐍𝐚𝐦𝐞 » ** `{name}`\n\n"
            f"**⏳Uploading Careerwill (CW) videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'utkarshapp' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 𝐍𝐚𝐦𝐞 » ** `{name}`\n\n"
            f"**⏳Uploading Utkarsh videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'studyiq' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 𝐍𝐚𝐦𝐞 » ** `{name}`\n\n"
            f"**⏳Uploading StudyIQ videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'kgs-v2.akamaized.net' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 𝐍𝐚𝐦𝐞 » ** `{name}`\n\n"
            f"**⏳Uploading Khan Sir videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'videos.classplusapp.com' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 𝐍𝐚𝐦𝐞 » ** `{name}`\n\n"
            f"**⏳Uploading ClassPlus videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    else:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 𝐍𝐚𝐦𝐞 » ** `{name}`\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )  
    try:
        if thumb == "no":
            thumbnail = f"{filename}.jpg"
        else:
            thumbnail = thumb
    except Exception as e:
        await m.reply_text(str(e))

    dur = int(duration(filename))
    processing_msg = await m.reply_text(emoji)
    
    # Check if the file size exceeds 1.8GB
    max_size = 1.8 * 1024 * 1024 * 1024  # 1.8GB in bytes
    file_size = os.path.getsize(filename)
    
    if file_size > max_size:
        # Notify user that the video is being split
        splitting_msg = await m.reply_text("🛠 **Splitting video into parts**...\n\n╰────⌈**𝗣𝗔𝗧𝗛𝗔𝗡❤️(@ALTAFPATHAN)**⌋────╯\n")
        
        # Split the video into parts
        parts = split_video(filename, max_size)
        parts.sort(key=lambda x: int(x.split('_')[-1].split('.')[0]))  # Sort by part number
        
        # Upload each part
        for i, part in enumerate(parts):
            part_dur = int(duration(part))
            await splitting_msg.edit_text(f"📤 **𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆** Part {i + 1} of {len(parts)}...\n\n╰────⌈**𝗣𝗔𝗧𝗛𝗔𝗡❤️(@ALTAFPATHAN)**⌋────╯\n")
            try:
                part_caption = f"⋅ ⋅ ─ ─ **Part {i + 1}** ─ ─ ⋅ ⋅ \n{cc}"
                await m.reply_video(part, caption=part_caption, supports_streaming=True, height=720, width=1280, thumb=thumbnail, duration=part_dur)
            except Exception:
                await m.reply_document(part, caption=part_caption)
            os.remove(part)
            await asyncio.sleep(3)
        
        # Delete the splitting message after all parts are uploaded
        await splitting_msg.delete()
    else:
        try:
            await m.reply_video(filename, caption=cc, supports_streaming=True, height=720, width=1280, thumb=thumbnail, duration=dur)
        except Exception:
            await m.reply_document(filename, caption=cc)
    
    await processing_msg.delete(True)
    await reply.delete(True)
    os.remove(f"{filename}.jpg")
    os.remove(filename)

#------------- LOG CHANNEL HANDLER -------------------------

async def send_vid(bot: Client, m: Message, url, cc, filename, thumb, name, log_channel_id):
    emoji = get_next_emoji()
    subprocess.run(f'ffmpeg -y -i "{filename}" -ss 00:00:12 -vframes 1 "{filename}.jpg"', shell=True)
    if 'pw.jarviss.workers' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"**⏳Processing Physics Wallah (PW) videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'visionias' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"**⏳Uploading Vision IAS videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'brightcove' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"**⏳Uploading Careerwill (CW) videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'utkarshapp' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"**⏳Uploading Utkarsh videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'studyiq' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"**⏳Uploading StudyIQ videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ikunalx) ✨**⌋────╯"
        )
    else:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )    
    try:
        if thumb == "no":
            thumbnail = f"{filename}.jpg"
        else:
            thumbnail = thumb
    except Exception as e:
        await m.reply_text(str(e))
        return

    dur = int(duration(filename))
    # Displaying a temporary message while processing
    processing_msg = await m.reply_text(emoji)

    try:
        # Send video to user and capture the message
        message = await m.reply_video(filename, caption=cc, supports_streaming=True, height=720, width=1280, thumb=thumbnail, duration=dur)
        file_id = message.video.file_id  # Capture the file_id of the uploaded video
    except Exception as e:
        logging.error(e)
        # If sending video fails, send as document and capture the message
        message = await m.reply_document(filename, caption=cc)
        file_id = message.document.file_id  # Capture the file_id of the uploaded document

    await reply.delete (True)
    # Delete the temporary processing message
    await processing_msg.delete (True)
    # Send the video to the log channel using file_id

    try:
        await bot.send_video(log_channel_id, file_id, caption=cc, supports_streaming=True)
    except Exception as e:
        logging.error(f"Failed to send video to log channel: {e}")
        # If sending video fails, send as document using file_id
        await bot.send_document(log_channel_id, file_id, caption=cc)
    
    # Clean up
    os.remove(f"{filename}.jpg")
    os.remove(filename)

# ------------ For Watermark Follow this function --------------
async def send_video_watermark(bot: Client, m: Message, url, cc, filename, thumb, name, overlay):
    emoji = get_next_emoji()
    # Notify user about the watermarking process
    processing_text_msg_watermark = await m.reply_text(f"**Hold tight! We're adding some magic to your video ✨** -\n\n╰────⌈**𝗣𝗔𝗧𝗛𝗔𝗡❤️**⌋────╯")
    processing_msg_watermark = await m.reply_text("🐼")

    # FFmpeg command to overlay PNG watermark dynamically
    cmd = (
        f'ffmpeg -y -i "{filename}" -i "{overlay}" '
        f'-filter_complex "[0:v][1:v]overlay=W-overlay_w-10:H-overlay_h-10" '
        f'-c:a copy -preset ultrafast "{filename}_temp.mp4"'
    )

    # Execute the FFmpeg command
    subprocess.run(cmd, shell=True)

    # Delete the processing messages
    await processing_msg_watermark.delete(True)
    await processing_text_msg_watermark.delete(True)
    # Send the modified video
    if 'pw.jarviss.workers' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"**Processing Physics Wallah (PW) videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'visionias' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"**Uploading Vision IAS videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'brightcove' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"**Uploading Careerwill (CW) videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'utkarshapp' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"**Uploading Utkarsh videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    elif 'studyiq' in url:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"**Uploading StudyIQ videos may take some time.**\n\n"
            f"╰────⌈**✨ 𝗣𝗔𝗧𝗛𝗔𝗡 (@ALTAFPATHAN) ✨**⌋────╯"
        )
    else:
        reply = await m.reply_text(
            f"**🚀 𝐔𝐏𝐋𝐎𝐀𝐃𝐈𝐍𝐆!** 🚀\n\n"
            f"**🎬 Name » ** `{name}`\n"
            f"╰────⌈**✨ 𝐊𝐔𝐍𝐀𝐋 (@ikunalx) ✨**⌋────╯"
        )    
    try:
        if thumb == "no":
            thumb_cmd = f'ffmpeg -y -i "{filename}_temp.mp4" -ss 00:00:01 -vframes 1 "{filename}_thumb.jpg"'
            subprocess.run(thumb_cmd, shell=True)
            thumbnail = f"{filename}_thumb.jpg"
        else:
            thumbnail = thumb
    except Exception as e:
        await m.reply_text(str(e))

    # Extract duration of the video
    video_duration = duration(filename)
    dur = int(video_duration)

    # Displaying a temporary message while processing
    processing_msg = await m.reply_text(emoji)

    try:
        await m.reply_video(f"{filename}_temp.mp4", caption=cc, supports_streaming=True, height=720, width=1280, thumb=thumbnail, duration=dur)
    except Exception:
        await m.reply_document({filename}, caption=cc)
    await processing_msg.delete (True)
    await reply.delete(True)
    # Clean up temporary files
    os.remove(f"{filename}.jpg")
    os.remove(f"{filename}_temp.mp4")
    os.remove(filename)

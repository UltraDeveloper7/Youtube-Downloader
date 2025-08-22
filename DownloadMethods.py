from __future__ import unicode_literals
import os, sys
import yt_dlp as youtube_dl  # type: ignore

def _ffmpeg_dir():
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "ffmpeg") if os.path.exists(os.path.join(base, "ffmpeg")) else os.path.join(os.path.dirname(base), "tools", "ffmpeg")

class Download(object):
    def __init__(self, url, save_path, quality, playlist=False, download_type=False):
        self.url = url
        self.save_path = save_path
        self.qualities = {"Best": "1411", "Semi": "320", "Worst": "128"}
        self.quality = self.qualities[quality]
        self.playlist = playlist
        self.download_type = download_type  # False => audio, True => video

    @property
    def common_opts(self):
        fmt = "bestaudio/best" if not self.download_type else "bv*+ba/b"
        return {
            "verbose": False,
            "fixup": "detect_or_warn",
            "format": fmt,
            "outtmpl": os.path.join(self.save_path, "%(title)s.%(ext)s"),
            "noplaylist": self.playlist,
            "windowsfilenames": True,
            "prefer_ffmpeg": True,
            "ffmpeg_location": _ffmpeg_dir(),  # <- point yt-dlp to bundled ffmpeg
        }

    def mp3_download(self):
        self.download_type = False
        opts = dict(self.common_opts)
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": self.quality
        }]
        info = youtube_dl.YoutubeDL(opts).extract_info(self.url, download=True)
        return (info.get('title') or '').split("|")[0].strip()

    def mp4_download(self):
        self.download_type = True
        opts = dict(self.common_opts)
        opts["merge_output_format"] = "mp4"
        opts.setdefault("postprocessors", []).append({
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        })
        info = youtube_dl.YoutubeDL(opts).extract_info(self.url, download=True)
        return (info.get('title') or '').split("|")[0].strip()

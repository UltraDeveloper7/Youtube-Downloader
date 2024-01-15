from __future__ import unicode_literals
import yt_dlp as youtube_dl

class Download(object):
    def __init__(self, url, save_path, quality, playlist=False):
        self.url = url
        self.save_path = save_path
        self.qualities = {"Best": "1411", "Semi": "320", "Worst": "128"}
        self.quality = self.qualities[quality]
        self.playlist = playlist

    @property
    def common_opts(self):
        return {
            "verbose": False,
            "fixup"  : "detect_or_warn",
            "format" : "bestaudio/best",
            "outtmpl"     : self.save_path + "/%(title)s.%(ext)s",
            "noplaylist"  : self.playlist
        }

    def mp3_download(self):
        opts = self.common_opts
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec"  : "mp3",
            "preferredquality": self.quality
        }]
        opts["extractaudio"] = True
        download_object = youtube_dl.YoutubeDL(opts)
        download_object.download([self.url])

    def mp4_download(self):
        opts = self.common_opts
        opts["postprocessors"] = [{
            "key": "FFmpegVideoConvertor",
            "preferedformat"  : "mp4",
        }]
        download_object = youtube_dl.YoutubeDL(opts)
        download_object.download([self.url])

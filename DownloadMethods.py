from __future__ import unicode_literals
import yt_dlp as youtube_dl

class Download(object):
    def __init__(self, url, save_path, quality, playlist=False, download_type='audio'):
        self.url = url
        self.save_path = save_path
        self.qualities = {"Best": "1411", "Semi": "320", "Worst": "128"}
        self.quality = self.qualities[quality]
        self.playlist = playlist
        self.download_type = download_type

    @property
    def common_opts(self):
        return {
            "verbose": False,
            "fixup"  : "detect_or_warn",
            "format" : "bestaudio/best" if self.download_type == 'audio' else "bestvideo+bestaudio/best",
            "outtmpl"     : self.save_path + "/%(title)s.%(ext)s",
            "noplaylist"  : self.playlist
        }

    def mp3_download(self):
        self.download_type = 'audio'
        opts = self.common_opts
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec"  : "mp3",
            "preferredquality": self.quality
        }]
        opts["extractaudio"] = True
        download_object = youtube_dl.YoutubeDL(opts)
        #download_object.download([self.url])
        info = download_object.extract_info(self.url, download=True)
        song_name = info.get('title', None)
        # Split the song name on the "|" character and keep the first part
        song_name = song_name.split("|")[0].strip()
        return song_name

    def mp4_download(self):
        self.download_type = 'video'
        opts = self.common_opts
        opts["postprocessors"] = [{
            "key": "FFmpegVideoConvertor",
            "preferedformat"  : "mp4",
        }]
        download_object = youtube_dl.YoutubeDL(opts)
        #download_object.download([self.url])
        info = download_object.extract_info(self.url, download=True)
        song_name = info.get('title', None)
        # Split the song name on the "|" character and keep the first part
        song_name = song_name.split("|")[0].strip()
        return song_name

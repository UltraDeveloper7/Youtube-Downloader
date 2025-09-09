from __future__ import unicode_literals
import os
import re
import sys
import shutil
import yt_dlp as ydl  # type: ignore

def _resource_path(rel: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)

def _ffmpeg_exe():
    # Try bundled copies first
    candidates = [
        _resource_path(os.path.join("tools", "ffmpeg", "ffmpeg.exe")),
        _resource_path("ffmpeg.exe"),
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    # Fallback to PATH if the user already has ffmpeg
    return shutil.which("ffmpeg") or ""

class Download(object):
    def __init__(self, url, save_path, quality, playlist=False, download_type=False, progress_cb=None):
        self.url = url
        self.save_path = save_path
        self.qualities = {"Best": "1411", "Semi": "320", "Worst": "128"}
        self.quality = self.qualities.get(quality, self.qualities["Best"])
        self.playlist = playlist
        self.download_type = download_type  # False => audio, True => video
        self.progress_cb = progress_cb
        self._total_items = None
        self._current_index = 0 

    # ---------- emit to UI ----------
    def _emit(self, *, status=None, file_percent=None, overall_percent=None, info=None):
        if not self.progress_cb:
            return
        info = info or {}
        title = (info.get("title")
                 or os.path.basename(info.get("filepath") or info.get("filename") or "")
                 or "")
        idx = info.get("playlist_index")
        total_items = (info.get("n_entries") or info.get("playlist_count")
                       or info.get("playlist_n") or self._total_items)

        if overall_percent is None and idx and total_items and file_percent is not None:
            overall_percent = int(((int(idx) - 1) + (file_percent / 100.0)) * 100 / int(total_items))
            overall_percent = max(0, min(100, overall_percent))
        if not self.playlist and file_percent is not None and overall_percent is None:
            overall_percent = file_percent

        try:
            self.progress_cb({
                "status": status,
                "file_percent": file_percent,
                "overall_percent": overall_percent,
                "idx": idx,
                "total": total_items,
                "title": title,
            })
        except Exception:
            pass

    # ---------- super-reliable taps ----------
    class _YDL(ydl.YoutubeDL):
        def __init__(self, params=None, *, outer=None):
            self._outer = outer
            super().__init__(params or {})

        def _with_indexed_info(self, info):
            """Ensure playlist_index and n_entries are always present for the UI."""
            if not self._outer:
                return info
            if info is None:
                info = {}
            info = dict(info)  # copy
            # ensure index
            if self._outer.playlist and not info.get("playlist_index"):
                # if we've started processing, _current_index >= 1
                info["playlist_index"] = max(1, self._outer._current_index)
            # ensure total
            if self._outer._total_items and not info.get("n_entries"):
                info["n_entries"] = self._outer._total_items
            return info

        # internal progress reporter
        def report_progress(self, s):
            try:
                super().report_progress(s)
            finally:
                if not self._outer:
                    return
                info = self._with_indexed_info(s.get("info_dict"))
                downloaded = s.get("downloaded_bytes") or 0
                total = s.get("total_bytes") or s.get("total_bytes_estimate") or 0
                file_p = int(downloaded * 100 / total) if total else None
                self._outer._emit(status="downloading", file_percent=file_p, info=info)

        # starting per-file
        def process_info(self, info_dict):
            if self._outer:
                # advance our per-item counter for playlists
                if self._outer.playlist:
                    self._outer._current_index += 1
                info_for_ui = self._with_indexed_info(info_dict)
                self._outer._emit(status="starting", file_percent=0, info=info_for_ui)
            return super().process_info(info_dict)

        def report_destination(self, filename):
            super().report_destination(filename)
            if self._outer:
                base = os.path.basename(filename)
                title = os.path.splitext(base)[0]
                info = {"title": title}
                info = self._with_indexed_info(info)
                self._outer._emit(status="destination", file_percent=0, info=info)

        def _report_download_finished(self, filename):
            super()._report_download_finished(filename)
            if self._outer:
                base = os.path.basename(filename)
                title = os.path.splitext(base)[0]
                info = {"title": title}
                info = self._with_indexed_info(info)
                self._outer._emit(status="finished", file_percent=100, info=info)
                              
    # logger fallback (parses printed progress if hooks fail)
    class _Logger:
        _pct = re.compile(r'\b(\d{1,3}(?:\.\d)?)%')

        def __init__(self, outer):
            self.o = outer
            self.last_title = None

        def info(self, msg):   self._parse(msg)
        def debug(self, msg):  self._parse(msg)
        def warning(self, msg): pass
        def error(self, msg):   pass

        def _parse(self, msg: str):
            if "Destination:" in msg:
                t = os.path.basename(msg.split("Destination:", 1)[1].strip())
                if "." in t:
                    t = t.rsplit(".", 1)[0]
                self.last_title = t
                info = {"title": t}
                # inject index/total for the UI
                if self.o.playlist:
                    info["playlist_index"] = max(1, self.o._current_index or 1)
                if self.o._total_items:
                    info["n_entries"] = self.o._total_items
                self.o._emit(status="downloading", file_percent=1, info=info)
                return

            if "Merging formats into" in msg or "ExtractAudio" in msg:
                self.o._emit(status="postprocess", file_percent=100, info={"title": self.last_title or ""})

    # standard hooks as well
    def _percent_from_bytes(self, d):
        dl = d.get("downloaded_bytes") or 0
        total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        if total:
            return max(0, min(100, int(dl * 100 / total)))
        return 1 if dl else None

    def _yt_progress_hook(self, d):
        info = d.get("info_dict") or {}
        
        if self.playlist and not info.get("playlist_index"):
            info["playlist_index"] = max(1, self._current_index)
        if self._total_items and not info.get("n_entries"):
            info["n_entries"] = self._total_items
            
        status = d.get("status")
        if status == "downloading":
            self._emit(status="downloading", file_percent=self._percent_from_bytes(d), info=info)
        elif status == "finished":
            self._emit(status="finished", file_percent=100, info=info)

    def _yt_postprocessor_hook(self, d):
        info = d.get("info_dict") or {}
        if self.playlist and not info.get("playlist_index"):
            info["playlist_index"] = max(1, self._current_index)
        if self._total_items and not info.get("n_entries"):
            info["n_entries"] = self._total_items
        self._emit(status="postprocess", file_percent=100, info=info)

    # ---------- options ----------
    @property
    def common_opts(self):
        fmt = "bestaudio/best" if not self.download_type else "bv*+ba/b"
        ffmpeg_path = _ffmpeg_exe()
        opts = {
            "fixup": "detect_or_warn",
            "format": fmt,
            "outtmpl": os.path.join(self.save_path, "%(title)s.%(ext)s"),
            "noplaylist": not self.playlist,
            "windowsfilenames": True,
            "prefer_ffmpeg": True,
            "noprogress": False,
            # make logger receive progress lines if printed
            "progress_with_newline": True,
            "logger": self._Logger(self),
        }
        if ffmpeg_path:
            # yt-dlp accepts either the folder containing ffmpeg or the exe itself
            opts["ffmpeg_location"] = os.path.dirname(ffmpeg_path) if os.path.isfile(ffmpeg_path) else ffmpeg_path

        if self.progress_cb:
            opts["progress_hooks"] = [self._yt_progress_hook]
            opts["postprocessor_hooks"] = [self._yt_postprocessor_hook]
        return opts

    def _prefetch_total_items(self, base_opts):
        if not self.playlist or self._total_items is not None:
            return
        try:
            opts = dict(base_opts)
            opts.pop("progress_hooks", None)
            opts.pop("postprocessor_hooks", None)
            opts.pop("logger", None)
            y = self._YDL(opts, outer=None)
            info = y.extract_info(self.url, download=False)
            entries = info.get("entries") or []
            self._total_items = sum(1 for e in entries if e)
        except Exception:
            self._total_items = None

    # ---------- public API ----------
    def mp3_download(self):
        self.download_type = False
        self.current_index = 0
        opts = dict(self.common_opts)
        self._prefetch_total_items(opts)
        opts["postprocessors"] = [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": self.quality
        }]
        y = self._YDL(opts, outer=self)
        info = y.extract_info(self.url, download=True)
        return (info.get("title") or "").split("|")[0].strip()

    def mp4_download(self):
        self.download_type = True
        self.current_index = 0
        opts = dict(self.common_opts)
        self._prefetch_total_items(opts)
        opts["merge_output_format"] = "mp4"
        y = self._YDL(opts, outer=self)
        info = y.extract_info(self.url, download=True)
        return (info.get("title") or "").split("|")[0].strip()

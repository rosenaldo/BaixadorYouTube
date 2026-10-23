import os
import re
import sys
import shutil
import queue
import threading
import subprocess
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP_TITLE = "Baixador de vídeos"
YTDLP_CANDIDATES = ["yt-dlp.exe", "yt-dlp"]
FFMPEG_CANDIDATES = ["ffmpeg.exe", "ffmpeg"]


def app_dir():
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def find_program(names):
    # Prefer files beside the app so a portable copy uses its own dependencies.
    for name in names:
        candidate = os.path.join(app_dir(), name)
        if os.path.isfile(candidate):
            return candidate
    for name in names:
        found = shutil.which(name)
        if found:
            return found
    return None


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("720x590")
        self.root.minsize(620, 530)
        self.root.configure(bg="#f3f5f9")
        self.q = queue.Queue()
        self.worker = None
        self.cancel_event = threading.Event()
        self.active_process = None
        self.destination = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Videos", "YouTube"))
        self.url = tk.StringVar()
        self.quality = tk.StringVar(value="Melhor qualidade disponível")
        self.status = tk.StringVar(value="Pronto para baixar.")
        self._build()
        self.root.after(100, self._poll_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.close_app)

    def _build(self):
        outer = tk.Frame(self.root, bg="#f3f5f9", padx=24, pady=22)
        outer.pack(fill="both", expand=True)
        header = tk.Frame(outer, bg="#f3f5f9")
        header.pack(fill="x", pady=(0, 18))
        tk.Label(header, text="▶", font=("Segoe UI", 26, "bold"), fg="#c62828", bg="#f3f5f9").pack(side="left", padx=(0, 12))
        title_frame = tk.Frame(header, bg="#f3f5f9")
        title_frame.pack(side="left", fill="x", expand=True)
        tk.Label(title_frame, text="Baixar vídeo do YouTube", font=("Segoe UI", 20, "bold"), fg="#182230", bg="#f3f5f9").pack(anchor="w")
        tk.Label(title_frame, text="Cole o link, escolha a pasta e clique em Baixar.", font=("Segoe UI", 10), fg="#586579", bg="#f3f5f9").pack(anchor="w", pady=(4, 0))

        panel = tk.Frame(outer, bg="white", highlightbackground="#e1e6ef", highlightthickness=1, padx=20, pady=18)
        panel.pack(fill="both", expand=True)
        self._label(panel, "Link do vídeo")
        url_entry = ttk.Entry(panel, textvariable=self.url, font=("Segoe UI", 11))
        url_entry.pack(fill="x", ipady=7)
        url_entry.focus_set()

        self._label(panel, "Pasta onde salvar")
        dest_row = tk.Frame(panel, bg="white")
        dest_row.pack(fill="x")
        ttk.Entry(dest_row, textvariable=self.destination, font=("Segoe UI", 10)).pack(side="left", fill="x", expand=True, ipady=7)
        ttk.Button(dest_row, text="Escolher pasta…", command=self.choose_folder).pack(side="left", padx=(8, 0), ipady=3)

        self._label(panel, "Qualidade")
        ttk.Combobox(panel, textvariable=self.quality, state="readonly",
                     values=["Melhor qualidade disponível", "Até 1080p", "Até 720p"], font=("Segoe UI", 10)).pack(fill="x", ipady=4)
        tk.Label(panel, text="O programa prioriza MP4 com vídeo H.264 e áudio compatível com o Windows. O FFmpeg é necessário para juntar áudio e vídeo.",
                 font=("Segoe UI", 9), fg="#667085", bg="white", wraplength=610, justify="left").pack(anchor="w", pady=(10, 0))

        btnrow = tk.Frame(panel, bg="white")
        btnrow.pack(fill="x", pady=(18, 12))
        self.download_btn = ttk.Button(btnrow, text="Baixar vídeo", command=self.start_download)
        self.download_btn.pack(side="left", ipadx=20, ipady=7)
        self.cancel_btn = ttk.Button(btnrow, text="Cancelar", command=self.cancel_download, state="disabled")
        self.cancel_btn.pack(side="left", padx=(10, 0), ipadx=12, ipady=7)
        self.progress = ttk.Progressbar(panel, mode="indeterminate")
        self.progress.pack(fill="x", pady=(3, 10))
        tk.Label(panel, textvariable=self.status, font=("Segoe UI", 10), fg="#344054", bg="white", wraplength=610, justify="left").pack(anchor="w")
        tk.Label(outer, text="Use somente para vídeos que você tenha autorização para baixar. Respeite os direitos autorais e os termos do YouTube.",
                 font=("Segoe UI", 8), fg="#667085", bg="#f3f5f9", wraplength=650, justify="left").pack(anchor="w", pady=(12, 0))

    def _label(self, parent, text):
        tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"), fg="#253247", bg="white").pack(anchor="w", pady=(12, 6))

    def choose_folder(self):
        folder = filedialog.askdirectory(title="Escolha a pasta para salvar os vídeos", mustexist=True)
        if folder:
            self.destination.set(folder)

    def start_download(self):
        if self.worker and self.worker.is_alive():
            messagebox.showinfo("Download em andamento", "Aguarde o download atual terminar ou clique em Cancelar.")
            return
        url = self.url.get().strip()
        folder = self.destination.get().strip().strip('"')
        if not url:
            messagebox.showwarning("Falta o link", "Cole o link do vídeo do YouTube.")
            return
        if not re.match(r"^https?://", url, re.I):
            messagebox.showwarning("Link inválido", "Cole o endereço completo começando com https://")
            return
        if not any(host in url.lower() for host in ("youtube.com", "youtu.be", "youtube-nocookie.com")):
            messagebox.showwarning("Confira o link", "Este programa foi preparado para links do YouTube.")
            return
        if not folder:
            messagebox.showwarning("Falta a pasta", "Escolha uma pasta onde salvar o vídeo.")
            return
        try:
            os.makedirs(folder, exist_ok=True)
        except OSError as exc:
            messagebox.showerror("Pasta inválida", f"Não foi possível acessar a pasta:\n{exc}")
            return

        ytdlp = find_program(YTDLP_CANDIDATES)
        if not ytdlp:
            messagebox.showerror("yt-dlp não encontrado", "Coloque yt-dlp.exe na mesma pasta deste aplicativo.")
            return
        ffmpeg = find_program(FFMPEG_CANDIDATES)
        if not ffmpeg:
            messagebox.showerror("FFmpeg não encontrado", "Coloque ffmpeg.exe e ffprobe.exe na mesma pasta do aplicativo.")
            return

        quality = self.quality.get()
        if quality == "Até 1080p":
            limit = "1080"
        elif quality == "Até 720p":
            limit = "720"
        else:
            limit = None
        height = f"[height<={limit}]" if limit else ""
        # Only select H.264 MP4 video + AAC/M4A audio (or a compatible combined MP4).
        fmt = f"bv{height}[ext=mp4][vcodec^=avc1]+ba[ext=m4a][acodec^=mp4a]/b{height}[ext=mp4][vcodec^=avc1][acodec^=mp4a]"
        command = [ytdlp, "--newline", "--no-warnings", "--no-playlist", "--no-overwrites",
                   "--socket-timeout", "20", "--retries", "3", "--fragment-retries", "3",
                   "--ffmpeg-location", os.path.dirname(ffmpeg), "-P", folder, "-f", fmt,
                   "--merge-output-format", "mp4", "--windows-filenames", url]
        self.cancel_event.clear()
        self.download_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress.start(10)
        self.status.set("Iniciando download de um único vídeo…")
        self.worker = threading.Thread(target=self._download_worker, args=(command,), daemon=True)
        self.worker.start()

    def _download_worker(self, command):
        proc = None
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, encoding="utf-8", errors="replace",
                                    creationflags=flags, bufsize=1)
            self.active_process = proc
            # Read output in a separate thread so the worker can poll cancellation even
            # when yt-dlp has not printed a new line yet.
            def read_output():
                try:
                    for line in proc.stdout:
                        clean = line.strip()
                        if clean:
                            self.q.put(("line", clean))
                except Exception as exc:
                    self.q.put(("line", f"Aviso ao ler o log: {exc}"))
            reader = threading.Thread(target=read_output, daemon=True)
            reader.start()

            while proc.poll() is None:
                if self.cancel_event.wait(0.2):
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait()
                    self.q.put(("cancelled", "Download cancelado."))
                    return
            code = proc.wait()
            reader.join(timeout=2)
            if self.cancel_event.is_set():
                self.q.put(("cancelled", "Download cancelado."))
            elif code == 0:
                self.q.put(("done", "Download concluído! Confira a pasta de destino."))
            else:
                self.q.put(("error", f"O download falhou (código {code}). Veja a última mensagem exibida. Se o formato compatível não estiver disponível para esse vídeo, o programa avisará em vez de criar um MP4 incompatível."))
        except Exception as exc:
            self.q.put(("error", f"Erro ao executar o download: {exc}"))
        finally:
            self.active_process = None

    def cancel_download(self):
        self.cancel_event.set()
        self.status.set("Cancelando download…")

    def close_app(self):
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Download em andamento", "Deseja cancelar o download e fechar o programa?"):
                return
            self.cancel_event.set()
            if self.active_process and self.active_process.poll() is None:
                try:
                    self.active_process.terminate()
                except OSError:
                    pass
        self.root.destroy()

    def _poll_queue(self):
        try:
            while True:
                kind, msg = self.q.get_nowait()
                if kind == "line":
                    if any(token in msg.lower() for token in ("[download]", "destination", "merging", "error", "requested format", "already exists")):
                        self.status.set(msg[:240])
                elif kind in ("done", "error", "cancelled"):
                    self.progress.stop()
                    self.download_btn.configure(state="normal")
                    self.cancel_btn.configure(state="disabled")
                    self.status.set(msg)
                    if kind == "done":
                        messagebox.showinfo("Pronto", msg)
                    elif kind == "error":
                        messagebox.showerror("Não foi possível baixar", msg)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_queue)


if __name__ == "__main__":
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()

#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import cv2
import numpy as np
import sys

VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm")

def app_dir() -> Path:
    # Pasta do executável (PyInstaller) ou do script .py/.pyw
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def find_first_video(directory: Path) -> Path | None:
    for p in sorted(directory.iterdir()):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            return p
    return None

def downscale_high_quality(img, target_w, target_h):
    """Redução de alta qualidade: pyrDown sucessivos + ajuste Lanczos4. Nunca aumenta."""
    h, w = img.shape[:2]
    target_w = min(target_w, w)
    target_h = min(target_h, h)
    while (w // 2) >= target_w and (h // 2) >= target_h:
        img = cv2.pyrDown(img)
        h, w = img.shape[:2]
    if w > target_w or h > target_h:
        img = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
    return img

def parse_resolution(txt: str):
    try:
        w_str, h_str = txt.lower().strip().split("x")
        w, h = int(w_str), int(h_str)
        if w <= 0 or h <= 0:
            raise ValueError
        return w, h
    except Exception:
        raise ValueError('Use "LARGURAxALTURA", ex: 1920x1080')

def amostrar_indices(total_frames: int, n: int) -> np.ndarray:
    n = max(1, n)
    if total_frames <= 0:
        return np.array([0], dtype=int)
    n = min(n, total_frames)
    idx = np.linspace(0, total_frames - 1, num=n)
    idx = np.rint(idx).astype(int)
    idx = np.unique(np.clip(idx, 0, total_frames - 1))
    return idx

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Extrair Frames do Vídeo")
        self.geometry("600x330")
        self.resizable(False, False)

        self.var_input = tk.StringVar()
        self.var_output = tk.StringVar()
        self.var_count = tk.IntVar(value=100)
        self.var_format = tk.StringVar(value="png")
        self.var_jpg_quality = tk.IntVar(value=95)
        self.var_resize_mode = tk.StringVar(value="original")  # original | resolucao | escala
        self.var_resolution = tk.StringVar(value="1920x1080")
        self.var_scale = tk.DoubleVar(value=0.5)
        self.var_scale_str = tk.StringVar(value=f"{self.var_scale.get():.2f}")

        self.progress = tk.IntVar(value=0)
        self.status_text = tk.StringVar(value="Pronto.")
        self.cancel_event = threading.Event()
        self.worker_thread = None

        self._build_ui()
        self._update_fields_state()

        # Sugerir automaticamente vídeo e pasta ao abrir
        self._auto_defaults()

    # ------------------------ UI ------------------------

    def _build_ui(self):
        pad = {'padx': 10, 'pady': 6}

        frm_in = ttk.Frame(self); frm_in.pack(fill="x", **pad)
        ttk.Label(frm_in, text="Vídeo de entrada:").pack(side="left")
        e_in = ttk.Entry(frm_in, textvariable=self.var_input, width=64)
        e_in.bind("<KeyRelease>", lambda e: self._update_output_suggestion())
        e_in.bind("<FocusOut>", lambda e: self._update_output_suggestion())
        ttk.Button(frm_in, text="Selecionar...", command=self._sel_input).pack(side="right")
        e_in.pack(side="right", padx=6)

        frm_out = ttk.Frame(self); frm_out.pack(fill="x", **pad)
        ttk.Label(frm_out, text="Pasta de saída:").pack(side="left")
        self.e_out = ttk.Entry(frm_out, textvariable=self.var_output, width=64)
        ttk.Button(frm_out, text="Selecionar...", command=self._sel_output).pack(side="right")
        self.e_out.pack(side="right", padx=6)

        frm_qf = ttk.Frame(self); frm_qf.pack(fill="x", **pad)
        ttk.Label(frm_qf, text="Quantidade de imagens:").pack(side="left")
        sp_count = ttk.Spinbox(frm_qf, from_=1, to=100000, textvariable=self.var_count, width=8,
                    command=self._update_output_suggestion)
        sp_count.pack(side="left", padx=6)
        sp_count.bind("<KeyRelease>", lambda e: self._update_output_suggestion())
        sp_count.bind("<FocusOut>", lambda e: self._update_output_suggestion())

        ttk.Label(frm_qf, text="Formato:").pack(side="left", padx=(20, 0))
        cb = ttk.Combobox(frm_qf, textvariable=self.var_format, values=["png", "jpg"],
                          width=6, state="readonly")
        cb.pack(side="left", padx=6)
        cb.bind("<<ComboboxSelected>>", lambda e: self._update_fields_state())

        ttk.Label(frm_qf, text="JPEG qualidade:").pack(side="left", padx=(20, 0))
        self.sp_jpg = ttk.Spinbox(frm_qf, from_=0, to=100, textvariable=self.var_jpg_quality, width=6)
        self.sp_jpg.pack(side="left", padx=6)

        frm_mode = ttk.LabelFrame(self, text="Tamanho de saída (somente redução, nunca aumenta)")
        frm_mode.pack(fill="x", **pad)
        frm_mode.columnconfigure(1, weight=1)
        ttk.Radiobutton(frm_mode, text="Usar resolução original", value="original",
                        variable=self.var_resize_mode, command=self._on_mode_change).grid(row=0, column=0, sticky="w", padx=6, pady=4)
        ttk.Radiobutton(frm_mode, text="Definir resolução (WxH)", value="resolucao",
                        variable=self.var_resize_mode, command=self._on_mode_change).grid(row=1, column=0, sticky="w", padx=6, pady=4)
        ttk.Radiobutton(frm_mode, text="Usar escala (0.01 a 1)", value="escala",
                        variable=self.var_resize_mode, command=self._on_mode_change).grid(row=2, column=0, sticky="w", padx=6, pady=4)

        self.ent_res = ttk.Entry(frm_mode, textvariable=self.var_resolution, width=12)
        self.ent_res.grid(row=1, column=1, sticky="w", padx=6)
        self.ent_res.bind("<FocusOut>", lambda e: self._update_output_suggestion())

        self.scale_slider = ttk.Scale(frm_mode, from_=0.01, to=1.0, orient="horizontal",
                              variable=self.var_scale, command=lambda v: self._update_output_suggestion())
        self.scale_slider.grid(row=2, column=1, sticky="we", padx=6)

        self.lbl_scale_val = ttk.Label(frm_mode, textvariable=self.var_scale_str)
        self.lbl_scale_val.grid(row=2, column=2, sticky="w", padx=4)

        self.var_scale.trace_add("write", lambda *_: self.var_scale_str.set(f"{self.var_scale.get():.2f}"))
        frm_prog = ttk.Frame(self); frm_prog.pack(fill="x", **pad)
        self.pb = ttk.Progressbar(frm_prog, orient="horizontal", mode="determinate",
                                  maximum=100, variable=self.progress)
        self.pb.pack(fill="x", padx=2, pady=2)
        ttk.Label(frm_prog, textvariable=self.status_text).pack(anchor="w")

        frm_btn = ttk.Frame(self); frm_btn.pack(fill="x", **pad)
        self.btn_exec = ttk.Button(frm_btn, text="Executar", command=self._on_execute)
        self.btn_exec.pack(side="left")
        self.btn_cancel = ttk.Button(frm_btn, text="Cancelar", command=self._on_cancel, state="disabled")
        self.btn_cancel.pack(side="left", padx=6)
        ttk.Button(frm_btn, text="Sair", command=self.destroy).pack(side="right")

    # ------------------------ Lógica UI ------------------------

    def _on_mode_change(self):
        self._update_fields_state()
        self._update_output_suggestion()

    def _update_fields_state(self):
        mode = self.var_resize_mode.get()
        fmt = self.var_format.get()
        self.ent_res.configure(state="normal" if mode == "resolucao" else "disabled")
        state = "normal" if mode == "escala" else "disabled"
        self.scale_slider.configure(state=state)
        self.lbl_scale_val.configure(state=state)
        self.sp_jpg.configure(state="normal" if fmt == "jpg" else "disabled")

    def _sel_input(self):
        path = filedialog.askopenfilename(
            title="Selecione o vídeo",
            initialdir=str(app_dir()),
            filetypes=[("Vídeos", "*.mp4 *.mov *.mkv *.avi *.m4v *.webm"), ("Todos os arquivos", "*.*")]
        )
        if path:
            self.var_input.set(path)
            self._update_output_suggestion()

    def _sel_output(self):
        path = filedialog.askdirectory(title="Selecione a pasta de saída", initialdir=str(app_dir()))
        if path:
            self.var_output.set(path)

    def _on_cancel(self):
        self.cancel_event.set()
        self.status_text.set("Cancelando...")

    # ------------------------ Auto defaults ------------------------

    def _auto_defaults(self):
        # Detecta vídeo na mesma pasta e preenche input e sugestão de output
        vid = find_first_video(app_dir())
        if vid:
            self.var_input.set(str(vid))
            self._update_output_suggestion()

    def _update_output_suggestion(self):
        """Sugere <stem>_<count>f<largura>px se a saída estiver vazia ou se for uma sugestão antiga compatível."""
        # Só sugerir se o usuário não preencheu manualmente
        current_out = self.var_output.get().strip()
        in_path_str = self.var_input.get().strip()
        if not in_path_str:
            return

        in_path = Path(in_path_str)
        if not in_path.exists():
            return

        # Descobrir largura resultante para compor o nome
        try:
            cap = cv2.VideoCapture(str(in_path))
            if not cap.isOpened():
                return
            ok, frame0 = cap.read()
            cap.release()
            if not ok or frame0 is None:
                return
            h0, w0 = frame0.shape[:2]
        except Exception:
            return

        mode = self.var_resize_mode.get()
        count = max(1, int(self.var_count.get()))

        if mode == "resolucao":
            try:
                w_out, h_out = parse_resolution(self.var_resolution.get())
                w_out = min(w_out, w0); h_out = min(h_out, h0)
            except Exception:
                w_out = w0
        elif mode == "escala":
            try:
                scale_factor = float(self.var_scale.get())
                if scale_factor <= 0:
                    raise ValueError("Escala deve ser > 0.")
                w_out = max(1, int(round(w0 * scale_factor)))
                h_out = max(1, int(round(h0 * scale_factor)))
            except Exception:
                w_out = w0
        else:
            w_out = w0

        sug = in_path.parent / f"{in_path.stem}_{count}f-{w_out}px"

        current_name = Path(current_out).name if current_out else ""
        is_auto_suggestion = (
            not current_out or 
            current_out.endswith("_frames") or
            ("_" in current_name and "f-" in current_name and "px" in current_name and current_name.count("_") >= 1)
        )
        if is_auto_suggestion:
            self.var_output.set(str(sug))

    # ------------------------ Execução ------------------------

    def _on_execute(self):
        if self.worker_thread and self.worker_thread.is_alive():
            return
        try:
            in_path = self._resolve_input()
        except ValueError as e:
            messagebox.showerror("Erro", str(e))
            return

        out_dir = self._resolve_output_placeholder(in_path)
        self.status_text.set(f"Saída: {out_dir}")
        self.progress.set(0)
        self.cancel_event.clear()
        self.btn_exec.configure(state="disabled")
        self.btn_cancel.configure(state="normal")

        self.worker_thread = threading.Thread(target=self._worker, daemon=True)
        self.worker_thread.start()
        self.after(200, self._poll_worker)

    def _poll_worker(self):
        if self.worker_thread and self.worker_thread.is_alive():
            self.after(200, self._poll_worker)
        else:
            self.btn_exec.configure(state="normal")
            self.btn_cancel.configure(state="disabled")

    def _resolve_input(self) -> Path:
        p = self.var_input.get().strip()
        if p:
            path = Path(p)
            if not path.exists():
                raise ValueError("Vídeo de entrada não encontrado.")
            return path
        # fallback: procurar na pasta do app
        vid = find_first_video(app_dir())
        if not vid:
            raise ValueError("Nenhum vídeo encontrado e nenhum caminho informado.")
        return vid

    def _resolve_output_placeholder(self, in_path: Path) -> Path:
        out = self.var_output.get().strip()
        if out:
            return Path(out)
        return in_path.parent / f"{in_path.stem}_frames"

    def _worker(self):
        try:
            in_path = self._resolve_input()
            custom_out = self.var_output.get().strip()

            cap = cv2.VideoCapture(str(in_path))
            if not cap.isOpened():
                raise RuntimeError("Não foi possível abrir o vídeo.")

            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

            ok, frame0 = cap.read()
            if not ok or frame0 is None:
                raise RuntimeError("Não foi possível ler frames do vídeo.")
            h0, w0 = frame0.shape[:2]

            mode = self.var_resize_mode.get()
            if mode == "resolucao":
                w_out, h_out = parse_resolution(self.var_resolution.get())
                w_out = min(w_out, w0); h_out = min(h_out, h0)
            elif mode == "escala":
                scale = float(self.var_scale.get())
                if not (0 < scale <= 1):
                    raise ValueError("Escala deve estar entre 0 e 1.")
                w_out = max(1, int(round(w0 * scale)))
                h_out = max(1, int(round(h0 * scale)))
            else:
                w_out, h_out = w0, h0

            count = max(1, int(self.var_count.get()))
            indices = amostrar_indices(total_frames, count)

            # Pasta de saída padrão no formato pedido
            if custom_out:
                pasta_saida = Path(custom_out)
            else:
                pasta_saida = in_path.parent / f"{in_path.stem}_{count}f-{w_out}px"
            pasta_saida.mkdir(parents=True, exist_ok=True)

            fmt = self.var_format.get().lower()
            if fmt == "jpg":
                jpg_q = int(np.clip(int(self.var_jpg_quality.get()), 0, 100))
                imwrite_params = [cv2.IMWRITE_JPEG_QUALITY, jpg_q]
                ext = "jpg"
            else:
                imwrite_params = [cv2.IMWRITE_PNG_COMPRESSION, 3]
                ext = "png"

            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

            salvos = 0
            total = len(indices)
            for i, idx in enumerate(indices, start=1):
                if self.cancel_event.is_set():
                    break
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
                ok, frame = cap.read()
                if not ok or frame is None:
                    self._set_status(f"Falha ao ler frame {idx}. Continuando.")
                    self._set_progress(int(i * 100 / total))
                    continue

                if frame.shape[1] > w_out or frame.shape[0] > h_out:
                    frame = downscale_high_quality(frame, w_out, h_out)

                out_file = pasta_saida / f"frame_{i:04d}.{ext}"
                ok = cv2.imwrite(str(out_file), frame, imwrite_params)
                if ok:
                    salvos += 1

                self._set_status(f"Extraindo {i}/{total} → {out_file.name}")
                self._set_progress(int(i * 100 / total))

            cap.release()

            if self.cancel_event.is_set():
                self._set_status("Cancelado pelo usuário.")
                messagebox.showinfo("Cancelado", f"Processo cancelado.\nExtraídas: {salvos}")
            else:
                self._set_status(f"Concluído. Extraídas: {salvos}. Saída: {pasta_saida}")
                messagebox.showinfo(
                    "Concluído",
                    f"Vídeo: {in_path}\nFrames totais: {total_frames}\n"
                    f"Solicitadas: {count} | Extraídas: {salvos}\n"
                    f"Resolução vídeo: {w0}x{h0}\nResolução saída: {w_out}x{h_out}\n"
                    f"Saída: {pasta_saida}"
                )
        except Exception as e:
            messagebox.showerror("Erro", str(e))
            self._set_status(f"Erro: {e}")
        finally:
            self.progress.set(0)

    def _set_progress(self, val):
        self.progress.set(val)

    def _set_status(self, text):
        self.status_text.set(text)

if __name__ == "__main__":
    App().mainloop()

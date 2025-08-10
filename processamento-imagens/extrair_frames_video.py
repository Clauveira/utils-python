## Execute extrair_frames_video-gui.pyw para usar a interface gráfica

import argparse
import sys
from pathlib import Path
import cv2
import numpy as np


VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm")


def encontrar_primeiro_video_na_pasta_do_script() -> Path | None:
    pasta_script = Path(__file__).resolve().parent
    for p in sorted(pasta_script.iterdir()):
        if p.is_file() and p.suffix.lower() in VIDEO_EXTS:
            return p
    return None


def parse_args():
    p = argparse.ArgumentParser(
        description="Extrai N imagens de frames ao longo do vídeo, com resolução original, resolução fixa ou por escala."
    )
    p.add_argument(
        "-i", "--input",
        help="Caminho do vídeo de entrada. Padrão: primeiro vídeo encontrado na mesma pasta do script."
    )
    p.add_argument(
        "-o", "--output",
        help='Pasta de saída. Padrão: "<nome_arquivo_input>_<num_frames>f<largura_px>px".'
    )
    p.add_argument(
        "-n", "--count", type=int, default=100,
        help="Quantidade de fotos a extrair. Padrão: 100."
    )

    group = p.add_mutually_exclusive_group()
    group.add_argument(
        "-r", "--resolution",
        help='Resolução fixa LARGURAxALTURA (ex: "1920x1080"). Não usar junto com --scale.'
    )
    group.add_argument(
        "-s", "--scale", type=float,
        help="Fator de redução. Ex: 2 = metade (2x menor), 4 = 4x menor. Não usar junto com --resolution."
    )

    p.add_argument(
        "--format", choices=["jpg", "png"], default="png",
        help="Formato de saída. Padrão: png."
    )
    p.add_argument(
        "--jpg-quality", type=int, default=95,
        help="Qualidade do JPEG (0-100). Só se --format=jpg. Padrão: 95."
    )
    return p.parse_args()


def parse_resolution(txt: str) -> tuple[int, int]:
    try:
        w_str, h_str = txt.lower().split("x")
        w, h = int(w_str), int(h_str)
        if w <= 0 or h <= 0:
            raise ValueError
        return w, h
    except Exception:
        print('Erro: resolução inválida. Use "LARGURAxALTURA", ex: 1920x1080.', file=sys.stderr)
        sys.exit(2)


def amostrar_indices(total_frames: int, n: int) -> np.ndarray:
    n = max(1, n)
    if total_frames <= 0:
        return np.array([0], dtype=int)
    n = min(n, total_frames)
    idx = np.linspace(0, total_frames - 1, num=n)
    idx = np.rint(idx).astype(int)
    idx = np.unique(np.clip(idx, 0, total_frames - 1))
    return idx


def downscale_high_quality(img, target_w, target_h):
    """
    Redução de escala de alta qualidade:
    1) Aplica múltiplos pyrDown (gauss + /2) até ficar próximo do alvo.
    2) Finaliza com resize Lanczos4 para chegar exatamente na resolução desejada.
    Nunca aumenta a imagem.
    """
    h, w = img.shape[:2]

    # Garantir que não vamos aumentar
    target_w = min(target_w, w)
    target_h = min(target_h, h)

    # Etapa 1: reduções por /2 enquanto couber
    while (w // 2) >= target_w and (h // 2) >= target_h:
        img = cv2.pyrDown(img)  # filtro gaussiano + decimação por 2
        h, w = img.shape[:2]

    # Etapa 2: ajuste fino com Lanczos4 (somente se ainda for reduzir)
    if w > target_w or h > target_h:
        img = cv2.resize(img, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)

    return img


def main():
    args = parse_args()

    # Input
    if args.input:
        caminho_video = Path(args.input)
    else:
        encontrado = encontrar_primeiro_video_na_pasta_do_script()
        if not encontrado:
            print("Erro: nenhum vídeo encontrado na pasta do script e nenhum --input informado.", file=sys.stderr)
            sys.exit(1)
        caminho_video = encontrado

    if not caminho_video.exists():
        print(f"Erro: vídeo não encontrado: {caminho_video}", file=sys.stderr)
        sys.exit(1)

    cap = cv2.VideoCapture(str(caminho_video))
    if not cap.isOpened():
        print(f"Erro: não foi possível abrir o vídeo: {caminho_video}", file=sys.stderr)
        sys.exit(1)

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    # Ler um frame para saber resolução original
    ok, frame0 = cap.read()
    if not ok or frame0 is None:
        print("Erro: não foi possível ler frames do vídeo.", file=sys.stderr)
        sys.exit(1)
    h0, w0 = frame0.shape[:2]

    # Definir saída (apenas redução, nunca aumento)
    if args.resolution:
        w_out, h_out = parse_resolution(args.resolution)
        # clamp para não aumentar
        if w_out > w0 or h_out > h0:
            w_out = min(w_out, w0)
            h_out = min(h_out, h0)
    elif args.scale:
        if args.scale <= 0:
            print("Erro: --scale deve ser > 0.", file=sys.stderr)
            sys.exit(2)
        w_out = max(1, int(round(w0 / args.scale)))
        h_out = max(1, int(round(h0 / args.scale)))
    else:
        # padrão: manter tamanho (mas como você pediu apenas redução, não faremos aumento em nenhum caso)
        w_out, h_out = w0, h0

    # Pasta de saída
    if args.output:
        pasta_saida = Path(args.output)
    else:
        pasta_saida = caminho_video.parent / f"{caminho_video.stem}_{args.count}f{w_out}px"
    pasta_saida.mkdir(parents=True, exist_ok=True)

    # Voltar ao início
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    indices = amostrar_indices(total_frames, args.count)

    # Escrita
    ext = args.format.lower()
    if ext == "jpg":
        imwrite_params = [cv2.IMWRITE_JPEG_QUALITY, int(np.clip(args.jpg_quality, 0, 100))]
    else:
        imwrite_params = [cv2.IMWRITE_PNG_COMPRESSION, 3]

    salvos = 0
    for i, idx in enumerate(indices, start=1):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ok, frame = cap.read()
        if not ok or frame is None:
            continue

        # Redução de alta qualidade (sem aumento)
        if frame.shape[1] > w_out or frame.shape[0] > h_out:
            frame = downscale_high_quality(frame, w_out, h_out)
        # Se a resolução alvo for igual à original, não faz nada.

        arquivo = pasta_saida / f"frame_{i:04d}.{ext}"
        ok = cv2.imwrite(str(arquivo), frame, imwrite_params)
        if ok:
            salvos += 1

    cap.release()

    print(f"Vídeo: {caminho_video}")
    print(f"Total de frames no vídeo: {total_frames}")
    print(f"Solicitadas: {args.count} | Extraídas: {salvos}")
    print(f"Resolução do vídeo: {w0}x{h0}")
    print(f"Resolução de saída: {w_out}x{h_out}")
    print(f"Formato: {ext}")
    print(f"Saída: {pasta_saida.resolve()}")


if __name__ == "__main__":
    main()

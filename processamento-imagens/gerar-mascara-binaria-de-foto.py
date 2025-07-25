#pip install rembg

import os
import cv2
import numpy as np
from PIL import Image
from rembg import remove

def gerar_mascaras(pasta_entrada, pasta_saida, espessura_borda=0):
    os.makedirs(pasta_saida, exist_ok=True)
    imagens = [f for f in os.listdir(pasta_entrada) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

    for nome in imagens:
        caminho_entrada = os.path.join(pasta_entrada, nome)
        caminho_saida = os.path.join(pasta_saida, os.path.splitext(nome)[0] + '_mask.png')

        with Image.open(caminho_entrada) as img:
            mask = remove(img, only_mask=True).convert('L')
            mask_np = np.array(mask)
            _, mask_bin = cv2.threshold(mask_np, 127, 255, cv2.THRESH_BINARY)
            if espessura_borda > 0:
                kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (espessura_borda * 2 + 1, espessura_borda * 2 + 1))
                mask_bin = cv2.dilate(mask_bin, kernel, iterations=1)
            Image.fromarray(mask_bin).save(caminho_saida)

    print(f"{len(imagens)} máscaras geradas com espessura da borda = {espessura_borda}.")

ESPESSURA_BORDA = 10
PASTA_ENTRADA = "Input/FotosOriginal"

if __name__ == "__main__":
    gerar_mascaras(PASTA_ENTRADA, "Output_mask" + str(ESPESSURA_BORDA) + "/", espessura_borda=ESPESSURA_BORDA)

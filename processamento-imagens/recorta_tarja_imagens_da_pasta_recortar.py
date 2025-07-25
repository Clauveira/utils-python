import cv2
import os
import numpy as np

def recortar_tarja(imagem):
    img_gray = cv2.cvtColor(imagem, cv2.COLOR_BGR2GRAY)
    _, img_thresh = cv2.threshold(img_gray, 240, 255, cv2.THRESH_BINARY)
    altura, largura = img_thresh.shape
    for i in range(altura - 1, -1, -1):
        if img_thresh[i, 0] < 255:
            return imagem[:i+1, :]
    return imagem

def processar_pasta(pasta_origem, pasta_destino):
    os.makedirs(pasta_destino, exist_ok=True)
    for root, dirs, files in os.walk(pasta_origem):
        for nome_arquivo in files:
            if nome_arquivo.lower().endswith(('.png', '.jpg', '.jpeg')):
                caminho_completo = os.path.join(root, nome_arquivo)
                imagem = cv2.imread(caminho_completo)
                if imagem is not None:
                    imagem_sem_tarja = recortar_tarja(imagem)
                    caminho_destino = os.path.join(pasta_destino, os.path.relpath(root, pasta_origem))
                    os.makedirs(caminho_destino, exist_ok=True)
                    caminho_destino_imagem = os.path.join(caminho_destino, nome_arquivo)
                    cv2.imwrite(caminho_destino_imagem, imagem_sem_tarja)
                    print(f"Imagem processada e salva: {caminho_destino_imagem}")

pasta_origem = './recortar'
pasta_destino = './recortado'
processar_pasta(pasta_origem, pasta_destino)

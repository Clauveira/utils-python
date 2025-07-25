import os

extensoes_imagens = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']

for arquivo in os.listdir():
    if any(arquivo.lower().endswith(ext) for ext in extensoes_imagens):
        nome_base = os.path.splitext(arquivo)[0]
        arquivo_txt = f"{nome_base}.txt"
        with open(arquivo_txt, 'w') as f:
            pass
print("Arquivos .txt gerados para cada imagem na pasta.")

import os
import base64
import mimetypes

def is_image_file(file_path):
    mime_type, _ = mimetypes.guess_type(file_path)
    return mime_type is not None and mime_type.startswith('image')

def convert_image_to_base64(image_path):
    try:
        with open(image_path, 'rb') as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
        return encoded_string
    except Exception as e:
        print(f"Erro ao converter {image_path}: {e}")
        return None

def save_base64_to_txt(base64_string, txt_path):
    try:
        with open(txt_path, 'w') as txt_file:
            txt_file.write(base64_string)
        print(f"Salvo: {txt_path}")
    except Exception as e:
        print(f"Erro ao salvar {txt_path}: {e}")

def main():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    print(f"Diretório atual: {current_dir}")
    files = os.listdir(current_dir)
    image_files = [f for f in files if is_image_file(os.path.join(current_dir, f))]
    if not image_files:
        print("Nenhuma imagem encontrada na pasta.")
        return
    print(f"Imagens encontradas: {len(image_files)}")
    for image in image_files:
        image_path = os.path.join(current_dir, image)
        base64_str = convert_image_to_base64(image_path)
        
        if base64_str:
            base_name, _ = os.path.splitext(image)
            txt_filename = f"{base_name}.txt"
            txt_path = os.path.join(current_dir, txt_filename)
            save_base64_to_txt(base64_str, txt_path)

if __name__ == "__main__":
    main()
    print("- - Finalizou. - -")
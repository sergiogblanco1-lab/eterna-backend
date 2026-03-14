import subprocess

imagenes = []

for foto in fotos:
    contenido = await foto.read()
    ruta = os.path.join(folder, foto.filename)

    with open(ruta, "wb") as f:
        f.write(contenido)

    imagenes.append(ruta)

# crear lista para ffmpeg
lista_path = os.path.join(folder, "lista.txt")

with open(lista_path, "w") as f:
    for img in imagenes:
        f.write(f"file '{img}'\n")
        f.write("duration 2\n")

video_path = os.path.join(folder, "video.mp4")

subprocess.run([
    "ffmpeg",
    "-f", "concat",
    "-safe", "0",
    "-i", lista_path,
    "-vsync", "vfr",
    "-pix_fmt", "yuv420p",
    video_path
])

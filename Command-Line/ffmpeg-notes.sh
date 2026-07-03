# Use this to export a sequence of *.jpg files (frames) into a single .mp4 video:
export JPG_FOLDER="C:/dev/testing/containing-folder" && ffmpeg -framerate 5 -i "$JPG_FOLDER/Your File Name%d.jpg" -vf "scale=trunc(iw*0.25/2)*2:trunc(ih*0.25/2)*2" -c:v libx264 -pix_fmt yuv420p -y "$JPG_FOLDER/out.mp4"

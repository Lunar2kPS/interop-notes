from PIL import Image
import numpy as np

file_path = "../../Scene View Render (Black).png"
print(f"Opening image file at: \"{file_path}\"")

image = Image.open(file_path)
pixels = np.array(image)

# NOTE: np.array(image) returns a 3D array, indexable by pixels[row (y), column (x), channel (0=R, 1=G, 2=B, 3=A)]!
# Red values can be grabbed easily with pixels[..., 0].
# Green:                                pixels[..., 1].
# Blue:                                 pixels[..., 2].
# Alpha:                                pixels[..., 3].

red_values = pixels[..., 0]
values, counts = np.unique(red_values, return_counts=True)
width = red_values.shape[1]
height = red_values.shape[0]

print(f"Image dimensions are {width} x {height}px (width x height).")
print(f"Image contains {image.mode} channels.")
print(f"Unique red channel values: {values}")
print(f"            Count of each: {counts}")
print(f"Additional info: {image.info}")
print(f"Each pixel's channel contains a single {np.array(image).dtype} value.")

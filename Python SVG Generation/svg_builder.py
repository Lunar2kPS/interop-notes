import shutil
import json
import cv2
import numpy as np

from xml.etree import ElementTree as etree
from skimage import measure
from shapely.geometry import Polygon
from pathlib import Path

COLORS = [ "blue", "cyan", "green", "yellow", "orange", "red", "magenta", "purple",
           "sienna", "darksalmon", "goldenrod", "darkolivegreen", "indigo", "wheat" ]

class ColorGetter:
    def __init__(self):
        self.colors = COLORS[:]
        self.next_index = 0

    def get_color(self):
        color = self.colors[self.next_index]
        self.next_index = (self.next_index + 1) % len(self.colors)
        return color

    def reset(self):
        self.next_index = 0

class SVGBuilder:
    def __init__(self, mask_path: Path, labels_path: Path, output_folder: Path):
        """Creates a set of SVG masks for each label within the mask."""

        self.mask_path = mask_path
        self.labels_path = labels_path
        self.output_folder = output_folder
        self.color_getter = ColorGetter()
        self.mask = cv2.imread(mask_path, cv2.IMREAD_GRAYSCALE)

    @staticmethod
    def mapper(value):
        if value > 0:
            return 255
        return 0

    @staticmethod
    def build_polygons(contours):
        polys = []
        for contour in contours:
            # Switch from row,col to x,y and remove padding
            for i in range(len(contour)):
                row, col = contour[i]
                contour[i] = (col - 1, row - 1)

            poly = Polygon(contour)
            poly = poly.simplify(1.0, preserve_topology=False)
            if poly.area > 100:
                polys.append(poly)
        return polys

    @staticmethod
    def extract_mask(mask, value: int):
        """Extracts a single value into its own 255/0 mask"""

        # Add a 1-pixel margin so that contours and things reach around
        mask = cv2.copyMakeBorder(mask, 1, 1, 1, 1, cv2.BORDER_CONSTANT, 0)

        mapper = np.vectorize(SVGBuilder.mapper)
        extracted = np.uint8(np.equal(np.array(mask), value))
        extracted = np.uint8(mapper(extracted))
        extracted_black = np.copy(extracted)

        cv2.floodFill(extracted_black, None, (0, 0), 255)
        return extracted, extracted_black

    def generate_svg(self):
        parts = self.load_part_labels(self.labels_path)
        for part in parts:
            value = part["value"]
            extracted, extracted_black = SVGBuilder.extract_mask(self.mask, value)
            contours = measure.find_contours(extracted, 10, positive_orientation="low")
            black_contours = measure.find_contours(extracted_black, 10, positive_orientation="high")
            part["polygons"] = SVGBuilder.build_polygons(contours)
            part["black_polys"] = SVGBuilder.build_polygons(black_contours)

        self.color_getter.reset()

        # NOTE: The apparent reversal in OpenCV follows NumPy's array convention, `image[y, x]`.
        #   The first index selects a **row,** which corresponds to the vertical coordinate `y`.
        #   OpenCV/NumPy address as [row, column], which translates to [y, x] and [height, width].
        display_width = self.mask.shape[1]
        display_height = self.mask.shape[0]

        file_name =  f"{self.mask_path.stem}.svg"
        etree.register_namespace("", "http://www.w3.org/2000/svg")
        rootElement = etree.XML(f"<svg viewBox=\"0 0 {display_width} {display_height }\" />")
        rootElement.set("xmlns", "http://www.w3.org/2000/svg")
        root = etree.ElementTree(rootElement)

        for part in parts:
            mask = etree.Element("mask", id=f"mask-{part['name']}")
            etree.SubElement(mask, "rect", x="0", y="0", width=str(display_width), height=str(display_height), fill="white", )
            for points in part["black_polys"]:
                svg = etree.XML(points.svg(opacity=1, fill_color="black"))
                svg.set("stroke","black")
                svg.set("stroke-width", "0")
                mask.append(svg)
            rootElement.append(mask)

            fill_color = self.color_getter.get_color()
            group = etree.Element("g", mask=f"url(#mask-{part['name']})", id=part['name'])
            for points in part["polygons"]:
                svg = etree.XML(points.svg(fill_color=fill_color, opacity=0.7))
                svg.set("stroke", fill_color)
                svg.set("stroke-width", "0.0")
                group.append(svg)
            rootElement.append(group)
        svg_path = self.output_folder / file_name

        # NOTE: Requires Python 3.9+:
        etree.indent(root, space=" " * 4)

        self.output_folder.mkdir(parents=True, exist_ok=True)
        # root.write(svg_path, encoding="utf-8")
        data = etree.tostring(root.getroot(), encoding="utf-8")
        with open(svg_path, "wb") as file:
            file.write(data)
            file.write(b"\n")

        return svg_path


    def load_part_labels(self, path):
        with open(path, "rt", encoding="utf-8") as f:
            labels = json.load(f)
        return [{"name": key, "value": value} for key, value in labels["values"].items()]


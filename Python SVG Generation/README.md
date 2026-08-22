# SVG Generator
## How it generates the SVG shapes
For each label defined in the JSON file, it:

1. Loads the grayscale mask using OpenCV.
2. Extracts pixels whose value equals that label’s numeric value.
3. Converts those pixels into a binary black/white mask.
4. Uses skimage.measure.find_contours to trace the boundaries of the labeled region.
5. Converts each contour from image coordinates (row, column) to SVG-style (x, y) coordinates.
6. Creates Shapely Polygon objects from the contours.
7. Simplifies the polygons with a tolerance of 1.0.
8. Discards polygons with an area of 100 or less.
9. Converts the remaining polygons to SVG <path> elements using Shapely’s .svg() method.
10. Places each part into its own SVG <g> group, with a unique color and mask.

from __future__ import annotations

from pathlib import Path
from statistics import mean
from typing import Any

from origin_ai_lab.models import CheckResult


MIN_WIDTH = 800
MIN_HEIGHT = 500
MIN_UNIQUE_COLORS = 8
MIN_NON_BACKGROUND_RATIO = 0.002
MIN_CONTENT_AREA_RATIO = 0.005
MIN_CONTRAST_STDDEV = 5.0


def evaluate_image_quality(image_path: Path) -> tuple[list[CheckResult], dict[str, Any]]:
    report: dict[str, Any] = {
        "schema_version": "visual-quality/v1",
        "image_path": str(image_path),
        "metrics": {},
        "checks": [],
    }
    if not image_path.exists():
        checks = [CheckResult("visual_image_exists", False, f"Missing image artifact: {image_path}")]
        report["checks"] = [check.to_dict() for check in checks]
        report["passed"] = False
        return checks, report

    try:
        from PIL import Image
    except ImportError:
        checks = [
            CheckResult(
                "visual_pillow_available",
                False,
                "Pillow is not installed, so pixel-level visual QA was skipped.",
                severity="warning",
            )
        ]
        report["checks"] = [check.to_dict() for check in checks]
        report["passed"] = True
        return checks, report

    with Image.open(image_path) as image:
        rgb = image.convert("RGB")
        width, height = rgb.size
        sample = rgb.copy()
        sample.thumbnail((512, 512))
        metrics = _measure_sample(sample)

    metrics.update(
        {
            "width": width,
            "height": height,
            "file_size_bytes": image_path.stat().st_size,
        }
    )

    checks = [
        CheckResult("visual_image_exists", True, f"Image artifact exists: {image_path.name}."),
        CheckResult(
            "visual_dimensions",
            width >= MIN_WIDTH and height >= MIN_HEIGHT,
            f"Image dimensions are {width}x{height}; target minimum is {MIN_WIDTH}x{MIN_HEIGHT}.",
            severity="warning",
        ),
        CheckResult(
            "visual_nonblank",
            metrics["unique_colors"] >= MIN_UNIQUE_COLORS
            and metrics["non_background_ratio"] >= MIN_NON_BACKGROUND_RATIO,
            (
                "Image has "
                f"{metrics['unique_colors']} sampled colors and "
                f"{metrics['non_background_ratio']:.4f} non-background pixel ratio."
            ),
        ),
        CheckResult(
            "visual_content_visible",
            metrics["content_area_ratio"] >= MIN_CONTENT_AREA_RATIO,
            f"Content area ratio is {metrics['content_area_ratio']:.4f}.",
        ),
        CheckResult(
            "visual_contrast",
            metrics["contrast_stddev"] >= MIN_CONTRAST_STDDEV,
            f"Sampled luminance standard deviation is {metrics['contrast_stddev']:.2f}.",
            severity="warning",
        ),
        CheckResult(
            "visual_not_clipped",
            metrics["min_margin_ratio"] > 0.0,
            f"Minimum content margin ratio is {metrics['min_margin_ratio']:.4f}.",
            severity="warning",
        ),
    ]
    report["metrics"] = metrics
    report["checks"] = [check.to_dict() for check in checks]
    report["passed"] = all(check.passed for check in checks if check.severity == "error")
    return checks, report


def _measure_sample(image: Any) -> dict[str, Any]:
    width, height = image.size
    pixel_source = image.get_flattened_data() if hasattr(image, "get_flattened_data") else image.getdata()
    pixels = list(pixel_source)
    background = _estimate_background_color(image)
    luminance_values = [_luminance(pixel) for pixel in pixels]
    luminance_mean = mean(luminance_values) if luminance_values else 0.0
    contrast = _stddev(luminance_values, luminance_mean)

    threshold = 12.0
    content_points: list[tuple[int, int]] = []
    unique_colors = set()
    index = 0
    for y in range(height):
        for x in range(width):
            pixel = pixels[index]
            unique_colors.add(pixel)
            if _color_distance(pixel, background) > threshold:
                content_points.append((x, y))
            index += 1

    content_count = len(content_points)
    total = max(len(pixels), 1)
    bbox = _content_bbox(content_points, width, height)
    margins = _margins_from_bbox(bbox) if bbox else None
    min_margin = min(margins) if margins else 0.0

    return {
        "sample_width": width,
        "sample_height": height,
        "sampled_pixel_count": len(pixels),
        "background_rgb": list(background),
        "unique_colors": len(unique_colors),
        "brightness_mean": luminance_mean,
        "contrast_stddev": contrast,
        "non_background_ratio": content_count / total,
        "content_bbox_norm": list(bbox) if bbox else None,
        "content_area_ratio": _bbox_area_ratio(bbox) if bbox else 0.0,
        "content_margins_norm": list(margins) if margins else None,
        "min_margin_ratio": min_margin,
    }


def _estimate_background_color(image: Any) -> tuple[int, int, int]:
    width, height = image.size
    coordinates = (
        (0, 0),
        (width - 1, 0),
        (0, height - 1),
        (width - 1, height - 1),
    )
    colors = [image.getpixel(point) for point in coordinates]
    return tuple(round(mean(channel)) for channel in zip(*colors))


def _content_bbox(points: list[tuple[int, int]], width: int, height: int) -> tuple[float, float, float, float] | None:
    if not points:
        return None
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return (
        min(xs) / max(width - 1, 1),
        min(ys) / max(height - 1, 1),
        max(xs) / max(width - 1, 1),
        max(ys) / max(height - 1, 1),
    )


def _bbox_area_ratio(bbox: tuple[float, float, float, float] | None) -> float:
    if bbox is None:
        return 0.0
    left, top, right, bottom = bbox
    return max(right - left, 0.0) * max(bottom - top, 0.0)


def _margins_from_bbox(bbox: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    left, top, right, bottom = bbox
    return (left, top, 1.0 - right, 1.0 - bottom)


def _luminance(pixel: tuple[int, int, int]) -> float:
    red, green, blue = pixel
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def _stddev(values: list[float], center: float) -> float:
    if not values:
        return 0.0
    return (sum((value - center) ** 2 for value in values) / len(values)) ** 0.5


def _color_distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    return sum((left - right) ** 2 for left, right in zip(a, b)) ** 0.5

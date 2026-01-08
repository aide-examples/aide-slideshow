#!/usr/bin/env python3
"""
imgPrepare - Image resizer for digital photo frames.

Resizes images to a target resolution (default 1920x1080) using various
strategies: padding, cropping, hybrid, or hybrid with stretching.

Can be used as:
- Standalone CLI tool: python imgPrepare.py input/ output/
- Imported module: from imgPrepare import process_folder_iter, PrepareConfig
"""

import argparse
import gc
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Generator

from PIL import Image, ImageDraw, ImageFont, ImageStat

try:
    import pillow_avif  # noqa: F401 - enables AVIF support
except ImportError:
    pass  # AVIF support optional


EPS = 1e-6
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".heic", ".avif"}


@dataclass
class PrepareConfig:
    """Configuration for image preparation."""
    input_dir: Path
    output_dir: Path
    mode: str = "hybrid-stretch"
    target_size: tuple[int, int] = (1920, 1080)
    pad_mode: str = "average"
    crop_min: float = 0.8
    stretch_max: float = 0.2
    no_stretch_limit: float = 0.4
    show_text: bool = False
    skip_existing: bool = True
    dry_run: bool = False
    flatten: bool = False
    verbose: bool = False
    quiet: bool = False


@dataclass
class PrepareProgress:
    """Progress info yielded during processing."""
    current: int
    total: int
    filepath: str
    output_path: str
    status: str  # 'processed', 'exists', 'error'
    error_message: str | None = None


def is_image_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTENSIONS


def ensure_jpg(filepath: Path) -> Path | None:
    """Convert non-JPG images to JPG if needed."""
    ext = filepath.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return filepath

    jpg_path = filepath.with_suffix(".jpg")
    if jpg_path.exists():
        return jpg_path

    try:
        img = Image.open(filepath).convert("RGB")
        img.save(jpg_path, "JPEG", quality=95)
        print(f"Converted: {filepath} -> {jpg_path}")
        return jpg_path
    except Exception as e:
        print(f"Error converting {filepath}: {e}", file=sys.stderr)
        return None


def resize_uniform(img: Image.Image, target_size: tuple[int, int]) -> Image.Image:
    return img.resize(target_size, Image.LANCZOS)


def pad_to_aspect(img: Image.Image, target_aspect: float, pad_mode: str) -> Image.Image:
    w, h = img.size
    aspect = w / h

    if abs(aspect - target_aspect) < EPS:
        return img

    if aspect > target_aspect:
        new_h = int(w / target_aspect)
        new_w = w
    else:
        new_w = int(h * target_aspect)
        new_h = h

    if pad_mode == "white":
        color = (255, 255, 255)
    elif pad_mode == "black":
        color = (0, 0, 0)
    elif pad_mode == "average":
        small = img.resize((max(1, w // 3), max(1, h // 3)))
        stat = ImageStat.Stat(small)
        r, g, b = [int(x) for x in stat.mean[:3]]
        color = (r, g, b)
    else:  # gray
        color = (128, 128, 128)

    new_img = Image.new("RGB", (new_w, new_h), color)
    new_img.paste(img, ((new_w - w) // 2, (new_h - h) // 2))
    return new_img


def crop_towards_aspect(
    img: Image.Image, target_aspect: float, max_crop_fraction: float
) -> tuple[Image.Image, float, bool]:
    w, h = img.size
    aspect = w / h

    if abs(aspect - target_aspect) < EPS:
        return img, 0.0, True

    if aspect > target_aspect:
        new_w = int(target_aspect * h)
        delta = w - new_w
        max_crop = int(w * max_crop_fraction)
        if delta > max_crop:
            new_w = w - max_crop
            delta = max_crop
        left = delta // 2
        right = w - (delta - left)
        cropped = img.crop((left, 0, right, h))
        return cropped, delta / w, abs((cropped.width / cropped.height) - target_aspect) < EPS
    else:
        new_h = int(w / target_aspect)
        delta = h - new_h
        max_crop = int(h * max_crop_fraction)
        if delta > max_crop:
            new_h = h - max_crop
            delta = max_crop
        top = delta // 2
        bottom = h - (delta - top)
        cropped = img.crop((0, top, w, bottom))
        return cropped, delta / h, abs((cropped.width / cropped.height) - target_aspect) < EPS


def mode_pad(img: Image.Image, target_size: tuple[int, int], pad_mode: str) -> Image.Image:
    target_aspect = target_size[0] / target_size[1]
    return resize_uniform(pad_to_aspect(img, target_aspect, pad_mode), target_size)


def mode_crop(img: Image.Image, target_size: tuple[int, int], crop_min: float) -> Image.Image:
    target_aspect = target_size[0] / target_size[1]
    max_crop_fraction = max(0.0, min(1.0, 1.0 - crop_min))
    cropped, _, _ = crop_towards_aspect(img, target_aspect, max_crop_fraction)
    return resize_uniform(cropped, target_size)


def mode_hybrid(
    img: Image.Image, target_size: tuple[int, int], crop_min: float, pad_mode: str
) -> Image.Image:
    target_aspect = target_size[0] / target_size[1]
    max_crop_fraction = max(0.0, min(1.0, 1.0 - crop_min))
    cropped, _, reached_exact = crop_towards_aspect(img, target_aspect, max_crop_fraction)
    if reached_exact:
        return resize_uniform(cropped, target_size)
    padded = pad_to_aspect(cropped, target_aspect, pad_mode)
    return resize_uniform(padded, target_size)


def mode_hybrid_stretch(
    img: Image.Image,
    target_size: tuple[int, int],
    crop_min: float,
    stretch_max: float,
    no_stretch_limit: float,
    pad_mode: str,
) -> Image.Image:
    target_aspect = target_size[0] / target_size[1]
    w0, h0 = img.size
    a0 = w0 / h0
    dev0 = abs(a0 / target_aspect - 1.0)

    # If deviation too large, just pad without crop or stretch
    if dev0 > no_stretch_limit + EPS:
        padded = pad_to_aspect(img, target_aspect, pad_mode)
        return resize_uniform(padded, target_size)

    max_crop_fraction = max(0.0, min(1.0, 1.0 - crop_min))
    cropped, _, reached_exact = crop_towards_aspect(img, target_aspect, max_crop_fraction)
    a1 = cropped.width / cropped.height

    if abs(a1 - target_aspect) < EPS:
        return resize_uniform(cropped, target_size)

    r_needed = target_aspect / a1
    anisotropy = abs(r_needed - 1.0)

    if anisotropy <= stretch_max + EPS:
        return cropped.resize(target_size, Image.LANCZOS)
    else:
        r_target = 1.0 + (stretch_max if r_needed > 1.0 else -stretch_max)
        new_w = max(1, int(round(cropped.width * r_target)))
        new_h = cropped.height
        stretched_partial = cropped.resize((new_w, new_h), Image.LANCZOS)
        padded = pad_to_aspect(stretched_partial, target_aspect, pad_mode)
        return resize_uniform(padded, target_size)


def add_text(img: Image.Image, text: str) -> Image.Image:
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 32)
    except OSError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), text, font=font)
    text_h = bbox[3] - bbox[1]
    x = 10
    y = img.height - text_h - 10
    draw.text((x, y), text, font=font, fill=(180, 180, 180))
    return img


def process_image(
    filepath: Path,
    output_dir: Path,
    prefix: str,
    mode: str,
    target_size: tuple[int, int],
    pad_mode: str,
    crop_min: float,
    stretch_max: float,
    no_stretch_limit: float,
    show_text: bool,
    skip_existing: bool,
    dry_run: bool,
    verbose: bool,
    quiet: bool,
) -> tuple[str, Path, str | None]:
    """
    Process a single image.

    Returns:
        tuple of (status, output_path, error_message)
        status: 'processed', 'exists', or 'error'
    """
    img = None
    out_img = None
    error_message = None

    try:
        jpg_path = ensure_jpg(filepath) if not dry_run else filepath
        if not jpg_path:
            return "error", Path(""), "Failed to convert to JPG"

        name = Path(filepath).stem
        if prefix:
            out_name = f"{prefix} - {name}.jpg"
            overlay_text = f"{prefix} - {name}"
        else:
            out_name = f"{name}.jpg"
            overlay_text = name

        out_path = output_dir / out_name

        if skip_existing and out_path.exists():
            if verbose:
                print(f"Exists: {out_path}")
            return "exists", out_path, None

        if dry_run:
            if not quiet:
                print(f"Would process: {filepath} -> {out_path}")
            return "processed", out_path, None

        img = Image.open(jpg_path).convert("RGB")

        if mode == "pad":
            out_img = mode_pad(img, target_size, pad_mode)
        elif mode == "crop":
            out_img = mode_crop(img, target_size, crop_min)
        elif mode == "hybrid":
            out_img = mode_hybrid(img, target_size, crop_min, pad_mode)
        elif mode == "hybrid-stretch":
            out_img = mode_hybrid_stretch(
                img, target_size, crop_min, stretch_max, no_stretch_limit, pad_mode
            )
        else:
            out_img = resize_uniform(img, target_size)

        if show_text:
            out_img = add_text(out_img, overlay_text)

        output_dir.mkdir(parents=True, exist_ok=True)
        out_img.save(out_path, "JPEG", quality=95)
        if not quiet:
            print(f"Saved: {out_path}")
        return "processed", out_path, None

    except Exception as e:
        error_message = str(e)
        print(f"Error processing {filepath}: {e}", file=sys.stderr)
        return "error", Path(""), error_message

    finally:
        # Explicit cleanup to release memory
        if img is not None:
            img.close()
            del img
        if out_img is not None:
            out_img.close()
            del out_img


def count_image_files(input_dir: Path) -> int:
    """Count total image files in directory (for progress estimation)."""
    count = 0
    if not input_dir.is_dir():
        return 0
    for root, _, files in os.walk(input_dir):
        for filename in files:
            if is_image_file(filename):
                count += 1
    return count


def list_subdirs(directory: Path) -> list[str]:
    """List all subdirectories (for UI folder selection)."""
    subdirs = []
    if not directory.is_dir():
        return subdirs
    for root, dirs, _ in os.walk(directory):
        rel_root = Path(root).relative_to(directory)
        for d in dirs:
            subdir = str(rel_root / d) if rel_root != Path(".") else d
            subdirs.append(subdir)
    return sorted(subdirs)


def process_folder_iter(config: PrepareConfig) -> Generator[PrepareProgress, None, dict[str, int]]:
    """
    Process all images with progress reporting via generator.

    Yields PrepareProgress for each file processed.
    Returns final counts dict when complete.

    Usage:
        config = PrepareConfig(input_dir=Path("in"), output_dir=Path("out"))
        gen = process_folder_iter(config)
        for progress in gen:
            print(f"{progress.current}/{progress.total}: {progress.status}")
        # Generator returns final counts (access via StopIteration.value or wrapper)
    """
    # Collect files first to know total count
    files_to_process = []
    for root, _, files in os.walk(config.input_dir):
        root_path = Path(root)
        rel_path = root_path.relative_to(config.input_dir)

        if config.flatten:
            target_dir = config.output_dir
            prefix = "" if rel_path == Path(".") else str(rel_path).replace(os.sep, " - ")
        else:
            target_dir = config.output_dir / rel_path
            prefix = ""

        for filename in files:
            if is_image_file(filename):
                files_to_process.append((root_path / filename, target_dir, prefix))

    total = len(files_to_process)
    counts = {"processed": 0, "exists": 0, "error": 0}

    for i, (filepath, target_dir, prefix) in enumerate(files_to_process, 1):
        status, out_path, error_msg = process_image(
            filepath,
            target_dir,
            prefix,
            config.mode,
            config.target_size,
            config.pad_mode,
            config.crop_min,
            config.stretch_max,
            config.no_stretch_limit,
            config.show_text,
            config.skip_existing,
            config.dry_run,
            config.verbose,
            config.quiet,
        )
        counts[status] = counts.get(status, 0) + 1

        yield PrepareProgress(
            current=i,
            total=total,
            filepath=str(filepath),
            output_path=str(out_path),
            status=status,
            error_message=error_msg,
        )

        # Force garbage collection every 10 images to keep memory in check
        if i % 10 == 0:
            gc.collect()

    # Final cleanup
    gc.collect()
    return counts


def process_folder(
    input_dir: Path,
    output_dir: Path,
    mode: str,
    target_size: tuple[int, int],
    pad_mode: str,
    crop_min: float,
    stretch_max: float,
    no_stretch_limit: float,
    show_text: bool,
    skip_existing: bool,
    dry_run: bool,
    flatten: bool,
    verbose: bool,
    quiet: bool,
) -> dict[str, int]:
    """Process all images in folder recursively. Returns counts by status."""
    config = PrepareConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        mode=mode,
        target_size=target_size,
        pad_mode=pad_mode,
        crop_min=crop_min,
        stretch_max=stretch_max,
        no_stretch_limit=no_stretch_limit,
        show_text=show_text,
        skip_existing=skip_existing,
        dry_run=dry_run,
        flatten=flatten,
        verbose=verbose,
        quiet=quiet,
    )

    counts = {"processed": 0, "exists": 0, "error": 0}
    gen = process_folder_iter(config)

    # Consume the generator, collecting final counts
    try:
        while True:
            progress = next(gen)
            counts[progress.status] = counts.get(progress.status, 0) + 1
    except StopIteration as e:
        if e.value:
            counts = e.value

    return counts


def parse_size(value: str) -> tuple[int, int]:
    """Parse WxH format into tuple."""
    try:
        w, h = value.lower().split("x")
        return (int(w), int(h))
    except ValueError:
        raise argparse.ArgumentTypeError(f"Invalid size format: {value}. Use WxH (e.g., 1920x1080)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Resize images for digital photo frames.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /photos/input /photos/output
  %(prog)s -m hybrid-stretch --crop-min 0.8 --stretch-max 0.2 input/ output/
  %(prog)s --size 1280x720 --pad-mode black input/ output/
""",
    )

    parser.add_argument("input_dir", type=Path, help="Source directory with images")
    parser.add_argument("output_dir", type=Path, help="Destination directory for processed images")

    parser.add_argument(
        "-m", "--mode",
        choices=["pad", "crop", "hybrid", "hybrid-stretch"],
        default="hybrid-stretch",
        help="Resize mode (default: hybrid-stretch)",
    )
    parser.add_argument(
        "-s", "--size",
        type=parse_size,
        default=(1920, 1080),
        metavar="WxH",
        help="Target size (default: 1920x1080)",
    )
    parser.add_argument(
        "--pad-mode",
        choices=["gray", "white", "black", "average"],
        default="average",
        help="Padding color (default: average)",
    )
    parser.add_argument(
        "--crop-min",
        type=float,
        default=0.8,
        metavar="FLOAT",
        help="Minimum image retention when cropping, 0.0-1.0 (default: 0.8)",
    )
    parser.add_argument(
        "--stretch-max",
        type=float,
        default=0.2,
        metavar="FLOAT",
        help="Maximum stretch factor for hybrid-stretch mode (default: 0.2)",
    )
    parser.add_argument(
        "--no-stretch-limit",
        type=float,
        default=0.4,
        metavar="FLOAT",
        help="Aspect deviation limit beyond which no stretching is applied (default: 0.4)",
    )
    parser.add_argument(
        "-t", "--text",
        action="store_true",
        help="Overlay filename on image",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Process all images, even if output already exists",
    )
    parser.add_argument(
        "-n", "--dry-run",
        action="store_true",
        help="Show what would be processed without actually doing it",
    )
    parser.add_argument(
        "--flatten",
        action="store_true",
        help="Flatten output: all images in output root (default: preserve subfolder structure)",
    )

    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose output (show all files including skipped)",
    )
    verbosity.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Quiet output (only show errors and summary)",
    )

    args = parser.parse_args()

    if not args.input_dir.is_dir():
        print(f"Error: Input directory does not exist: {args.input_dir}", file=sys.stderr)
        return 1

    counts = process_folder(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        mode=args.mode,
        target_size=args.size,
        pad_mode=args.pad_mode,
        crop_min=args.crop_min,
        stretch_max=args.stretch_max,
        no_stretch_limit=args.no_stretch_limit,
        show_text=args.text,
        skip_existing=not args.no_skip,
        dry_run=args.dry_run,
        flatten=args.flatten,
        verbose=args.verbose,
        quiet=args.quiet,
    )

    prefix = "Dry run: " if args.dry_run else ""
    parts = []
    if counts["processed"]:
        parts.append(f"Processed: {counts['processed']}")
    if counts["exists"]:
        parts.append(f"Skipped (exists): {counts['exists']}")
    if counts["error"]:
        parts.append(f"Errors: {counts['error']}")

    if parts:
        print(f"\n{prefix}{', '.join(parts)}")
    else:
        print(f"\n{prefix}No images found.")

    return 1 if counts["error"] else 0


if __name__ == "__main__":
    sys.exit(main())

import argparse
import asyncio
import json
import os
import sys
import logging
from pathlib import Path

from bingart import (
    BingArt,
    Model,
    Aspect,
    AuthCookieError,
    PromptRejectedError,
    __version__,
)


EXIT_SUCCESS = 0
EXIT_AUTH_ERROR = 1
EXIT_PROMPT_REJECTED = 2
EXIT_GENERIC_ERROR = 3

MODEL_MAP = {
    "dalle": Model.DALLE,
    "gpt4o": Model.GPT4O,
    "mai1": Model.MAI1,
}

ASPECT_MAP = {
    "square": Aspect.SQUARE,
    "landscape": Aspect.LANDSCAPE,
    "portrait": Aspect.PORTRAIT,
}


def build_parser():
    parser = argparse.ArgumentParser(
        prog="bingart",
        description=(
            "bingart - Unofficial CLI for Bing Image & Video Creator.\n"
            "Generate AI-powered images and videos from the command line."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "examples:\n"
            '  bingart "sunset over mountains"\n'
            '  bingart "cyberpunk city" -m gpt4o -a landscape\n'
            '  bingart "dancing robot" -V -A -o json\n'
            '  bingart "abstract art" -o urls -d ./output\n'
            "\n"
            "authentication:\n"
            "  Auth is resolved in this order:\n"
            "    1. --cookie / -c flag\n"
            "    2. --auto / -A flag (browser cookie detection)\n"
            "    3. BINGART_COOKIE environment variable\n"
            "    4. Interactive prompt\n"
            "\n"
            "exit codes:\n"
            "  0  success\n"
            "  1  authentication error\n"
            "  2  prompt rejected (content policy)\n"
            "  3  generic / unknown error\n"
        ),
    )

    parser.add_argument(
        "prompt",
        help="Text prompt for image/video generation.",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"bingart {__version__}",
    )

    model_group = parser.add_mutually_exclusive_group()
    model_group.add_argument(
        "-m",
        "--model",
        choices=list(MODEL_MAP.keys()),
        default="dalle",
        help="AI model to use (default: dalle).",
    )

    aspect_group = parser.add_mutually_exclusive_group()
    aspect_group.add_argument(
        "-a",
        "--aspect",
        choices=list(ASPECT_MAP.keys()),
        default="square",
        help="Aspect ratio (default: square).",
    )

    parser.add_argument(
        "-V",
        "--video",
        action="store_true",
        default=False,
        help="Generate a video instead of an image.",
    )

    auth_group = parser.add_mutually_exclusive_group()
    auth_group.add_argument(
        "-c",
        "--cookie",
        default=None,
        help="_U auth cookie value for Bing.",
    )
    auth_group.add_argument(
        "-A",
        "--auto",
        action="store_true",
        default=False,
        help="Auto-detect _U cookie from installed browsers.",
    )

    parser.add_argument(
        "-o",
        "--output",
        choices=["text", "json", "urls"],
        default="text",
        help="Output format (default: text). 'json' prints raw response, 'urls' prints one URL per line.",
    )

    parser.add_argument(
        "-d",
        "--download",
        default=None,
        metavar="DIR",
        help="Download generated images/video to DIR (created if it doesn't exist).",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose/debug logging output.",
    )

    return parser


def resolve_cookie(args):
    if args.cookie:
        return args.cookie, False
    if args.auto:
        return None, True
    env_cookie = os.environ.get("BINGART_COOKIE")
    if env_cookie:
        return env_cookie, False
    try:
        cookie = input("Enter your _U cookie value: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nAborted.", file=sys.stderr)
        sys.exit(EXIT_GENERIC_ERROR)
    if not cookie:
        print("Error: no cookie provided.", file=sys.stderr)
        sys.exit(EXIT_AUTH_ERROR)
    return cookie, False


async def download_file(url, dest_path, session=None):
    import urllib.request

    try:
        urllib.request.urlretrieve(url, str(dest_path))
        return True
    except Exception:
        pass
    try:
        from curl_cffi.requests import get

        resp = get(url, allow_redirects=True)
        if resp.status_code == 200:
            dest_path.write_bytes(resp.content)
            return True
    except Exception:
        pass
    return False


async def download_results(result, dest_dir, content_type):
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)

    if content_type == "video":
        video_url = result.get("video", {}).get("video_url")
        if not video_url:
            print("Warning: no video URL found in response.", file=sys.stderr)
            return
        ext = "mp4"
        filename = f"001.{ext}"
        dest_path = dest / filename
        print(f"Downloading video -> {dest_path}")
        ok = await download_file(video_url, dest_path)
        if ok:
            print(f"  Saved: {dest_path}")
        else:
            print(f"  Failed to download: {video_url}", file=sys.stderr)
        return

    images = result.get("images", [])
    if not images:
        print("Warning: no images found in response.", file=sys.stderr)
        return

    for i, img in enumerate(images, 1):
        url = img.get("url")
        if not url:
            continue
        ext = "jpg"
        if ".png" in url:
            ext = "png"
        filename = f"{i:03d}.{ext}"
        dest_path = dest / filename
        print(f"Downloading image {i}/{len(images)} -> {dest_path}")
        ok = await download_file(url, dest_path)
        if ok:
            print(f"  Saved: {dest_path}")
        else:
            print(f"  Failed to download: {url}", file=sys.stderr)


def format_text(result, content_type):
    lines = []
    if content_type == "video":
        video_url = result.get("video", {}).get("video_url", "N/A")
        lines.append(f"Prompt: {result.get('prompt', 'N/A')}")
        lines.append(f"Video URL: {video_url}")
    else:
        lines.append(f"Model: {result.get('model', 'N/A')}")
        lines.append(f"Aspect: {result.get('aspect', 'N/A')}")
        lines.append(f"Enhanced Prompt: {result.get('prompt', 'N/A')}")
        images = result.get("images", [])
        lines.append(f"Images ({len(images)}):")
        for idx, img in enumerate(images, 1):
            lines.append(f"  [{idx}] {img.get('url', 'N/A')}")
    return "\n".join(lines)


def format_urls(result, content_type):
    urls = []
    if content_type == "video":
        video_url = result.get("video", {}).get("video_url")
        if video_url:
            urls.append(video_url)
    else:
        for img in result.get("images", []):
            url = img.get("url")
            if url:
                urls.append(url)
    return "\n".join(urls)


async def run(args):
    cookie_val, use_auto = resolve_cookie(args)
    model = MODEL_MAP[args.model]
    aspect = ASPECT_MAP[args.aspect]
    content_type = "video" if args.video else "image"

    logger = logging.getLogger("bingart")
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        logger.addHandler(handler)
        logger.debug("Model: %s", args.model)
        logger.debug("Aspect: %s", args.aspect)
        logger.debug("Content type: %s", content_type)
        logger.debug("Output format: %s", args.output)
        if args.download:
            logger.debug("Download dir: %s", args.download)
        logger.debug("Auth: %s", "auto-detect" if use_auto else "cookie")

    if use_auto:
        bing = BingArt(auto=True)
    else:
        bing = BingArt(auth_cookie_U=cookie_val)

    try:
        result = await bing.generate(
            args.prompt,
            model=model,
            aspect=aspect,
            content_type=content_type,
        )
    finally:
        await bing.close()

    if args.output == "json":
        print(json.dumps(result, indent=2))
    elif args.output == "urls":
        print(format_urls(result, content_type))
    else:
        print(format_text(result, content_type))

    if args.download:
        await download_results(result, args.download, content_type)


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        asyncio.run(run(args))
    except AuthCookieError as e:
        print(f"Auth error: {e}", file=sys.stderr)
        sys.exit(EXIT_AUTH_ERROR)
    except PromptRejectedError as e:
        print(f"Prompt rejected: {e}", file=sys.stderr)
        sys.exit(EXIT_PROMPT_REJECTED)
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(EXIT_GENERIC_ERROR)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(EXIT_GENERIC_ERROR)


if __name__ == "__main__":
    main()

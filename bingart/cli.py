import argparse
import asyncio
import datetime
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
    "flash": Model.FLASH,
    "illustration": Model.ILLUSTRATION,
}

MODEL_DISPLAY = {
    Model.FLASH: "MAI-Image-2.5-Flash (Vivid and natural)",
    Model.ILLUSTRATION: "MAI-Image-2e (Stylized illustration)",
}

ASPECT_MAP = {
    "square": Aspect.SQUARE,
    "landscape": Aspect.LANDSCAPE,
    "portrait": Aspect.PORTRAIT,
}


_CODES = {
    "green": "\033[32m",
    "red": "\033[31m",
    "cyan": "\033[36m",
    "dim": "\033[2m",
    "bold": "\033[1m",
    "yellow": "\033[33m",
}


def _color(name, text, file=None):
    if os.environ.get("NO_COLOR"):
        return text
    target = file or sys.stdout
    if not target.isatty():
        return text
    code = _CODES.get(name)
    if not code:
        return text
    return f"{code}{text}\033[0m"


def _header(version, timestamp, model, aspect, content_type):
    lines = [
        f"bingart v{version}  ({timestamp})",
        f"  Creating: {content_type}",
        f"  Model:    {model}",
        f"  Aspect:   {aspect}",
    ]
    return _color("bold", "\n".join(lines))


def build_parser():
    parser = argparse.ArgumentParser(
        prog="bingart",
        description=(
            "bingart - create AI images and videos with Bing's Image Creator.\n\n"
            "You give it a text description (a 'prompt') and it generates pictures\n"
            "(or a video) using Bing's AI models. The result is printed as a list\n"
            "of links you can open in a browser, or saved to disk with --download."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "QUICK START\n"
            "  You need to be logged in to Bing. The easiest way is to let bingart\n"
            "  read the login cookie straight from a browser you are already using:\n\n"
            '      bingart "a cat wearing a tiny hat" -A\n\n'
            "  (The -A / --auto flag grabs your saved Bing session automatically.)\n"
            "  If that does not work, copy your _U cookie manually with --cookie.\n\n"
            "CHOOSING A MODEL (-m)\n"
            "  flash         MAI-Image-2.5-Flash - 'Vivid and natural'. Photoreal,\n"
            "                detailed and dynamic results. Good all-round default. (default)\n"
            "  illustration  MAI-Image-2e - 'Stylized illustration'. Best for quick,\n"
            "                stylized / artistic pictures.\n\n"
            "CHOOSING A SHAPE (-a)\n"
            "  square    square, 1:1  - good for avatars, thumbnails.  (default)\n"
            "  landscape  wide, 7:4    - good for wallpapers, banners.\n"
            "  portrait   tall, 4:7    - good for phone screens, posters.\n\n"
            "OUTPUT FORMAT (-o)\n"
            "  text   human-readable summary with one link per image. (default)\n"
            "  json   the raw machine-readable response (for scripts).\n"
            "  urls   just the links, one per line (easy to pipe into other tools).\n\n"
            "EXAMPLES\n"
            '  bingart "sunset over mountains" -A\n'
            '  bingart "cyberpunk city" -m illustration -a landscape -A\n'
            '  bingart "a dancing robot" -V -A -o json\n'
            '  bingart "abstract art" -A -o urls -d ./my_images\n\n'
            "HOW LOGIN IS DECIDED (first match wins)\n"
            "  1. --cookie / -c  : a _U cookie you paste in directly\n"
            "  2. --auto   / -A  : read the cookie from an installed browser\n"
            "  3. BINGART_COOKIE  : an environment variable you have set\n"
            "  4. interactive prompt : you are asked to type the cookie\n\n"
            "EXIT CODES\n"
            "  0  success\n"
            "  1  login failed (cookie missing, invalid or expired)\n"
            "  2  prompt rejected (it broke Bing's content rules)\n"
            "  3  something else went wrong\n"
        ),
    )

    parser.add_argument(
        "prompt",
        help="What you want to create, written in plain words. "
        'Example: "a watercolor painting of a fox in the snow".',
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"bingart {__version__}",
    )

    parser.add_argument(
        "-m",
        "--model",
        choices=list(MODEL_MAP.keys()),
        default="flash",
        metavar="{flash,illustration}",
        help="Which AI model draws the result. Default: flash. "
        "See the CHOOSING A MODEL section below for what each one does.",
    )

    parser.add_argument(
        "-a",
        "--aspect",
        choices=list(ASPECT_MAP.keys()),
        default="square",
        metavar="{square,landscape,portrait}",
        help="Shape/size of the output. Default: square. "
        "See the CHOOSING A SHAPE section below for details.",
    )

    parser.add_argument(
        "-V",
        "--video",
        action="store_true",
        default=False,
        help="Make a VIDEO instead of an image. Leave this off to make pictures.",
    )

    auth_group = parser.add_mutually_exclusive_group()
    auth_group.add_argument(
        "-c",
        "--cookie",
        default=None,
        metavar="COOKIE",
        help="Your Bing '_U' login cookie, pasted as text. "
        "Get it from your browser's dev tools (see README). "
        "Cannot be used together with --auto.",
    )
    auth_group.add_argument(
        "-A",
        "--auto",
        action="store_true",
        default=False,
        help="Automatically grab the Bing login cookie from a browser installed "
        "on this computer (Chrome, Edge, Firefox, Brave, Opera, Vivaldi, Chromium). "
        "Cannot be used together with --cookie.",
    )

    parser.add_argument(
        "-o",
        "--output",
        choices=["text", "json", "urls"],
        default="text",
        metavar="{text,json,urls}",
        help="How the result is printed. Default: text. "
        "text = readable summary, json = raw data, urls = just the links.",
    )

    parser.add_argument(
        "-d",
        "--download",
        default=None,
        metavar="DIR",
        help="Save the generated images/video to a folder on disk (DIR). "
        "The folder is created if it does not already exist.",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=False,
        help="Show extra troubleshooting information while running.",
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
    import urllib.parse
    import urllib.request

    logger = logging.getLogger("bingart")
    loop = asyncio.get_running_loop()

    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        logger.debug("blocked non-http(s) URL: %s", url)
        return False

    try:
        await loop.run_in_executor(
            None, lambda: urllib.request.urlretrieve(url, str(dest_path))
        )
        return True
    except Exception as exc:
        logger.debug("urllib download failed for %s: %s", url, exc)

    try:
        from curl_cffi.requests import get

        def _curl_get():
            resp = get(url, allow_redirects=True)
            if resp.status_code == 200:
                dest_path.write_bytes(resp.content)
                return True
            return False

        if await loop.run_in_executor(None, _curl_get):
            return True
    except Exception as exc:
        logger.debug("curl_cffi download failed for %s: %s", url, exc)

    return False


async def download_results(result, dest_dir, content_type, model_name, aspect_name):
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime("%y%m%d-%H%M%S")

    if content_type == "video":
        video_url = result.get("video", {}).get("video_url")
        if not video_url:
            print(
                _color("red", "  no video URL found in response", file=sys.stderr),
                file=sys.stderr,
            )
            return
        filename = f"{model_name}_{aspect_name}_{ts}_001.mp4"
        dest_path = dest / filename
        print(f"  downloading -> {dest_path}")
        ok = await download_file(video_url, dest_path)
        if ok:
            print(_color("green", f"  saved: {dest_path}"))
        else:
            print(_color("red", f"  failed: {video_url}"), file=sys.stderr)
        return

    images = result.get("images", [])
    if not images:
        print(_color("red", "  no images found in response"), file=sys.stderr)
        return

    for i, img in enumerate(images, 1):
        url = img.get("url")
        if not url:
            continue
        ext = "jpg"
        if ".png" in url:
            ext = "png"
        filename = f"{model_name}_{aspect_name}_{ts}_{i:03d}.{ext}"
        dest_path = dest / filename
        print(f"  downloading {i}/{len(images)} -> {dest_path}")
        ok = await download_file(url, dest_path)
        if ok:
            print(_color("green", f"  saved: {dest_path}"))
        else:
            print(
                _color("red", f"  failed {i}/{len(images)}: {url}"),
                file=sys.stderr,
            )


def format_text(result, content_type):
    lines = []
    if content_type == "video":
        video_url = result.get("video", {}).get("video_url", "N/A")
        lines.append(f"  {_color('bold', 'Prompt:')}  {result.get('prompt', 'N/A')}")
        lines.append(f"  {_color('bold', 'Video:')}   {_color('cyan', video_url)}")
    else:
        lines.append(f"  {_color('bold', 'Model:')}   {model_display(result.get('model', 'N/A'))}")
        lines.append(f"  {_color('bold', 'Aspect:')}  {result.get('aspect', 'N/A')}")
        lines.append(f"  {_color('bold', 'Prompt:')}  {result.get('prompt', 'N/A')}")
        images = result.get("images", [])
        lines.append(f"  {_color('bold', f'Images ({len(images)}):')}")
        for idx, img in enumerate(images, 1):
            lines.append(f"    [{idx}] {_color('cyan', img.get('url', 'N/A'))}")
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


def model_display(model):
    if isinstance(model, Model):
        return MODEL_DISPLAY.get(model, model.name)
    try:
        return MODEL_DISPLAY.get(Model[model], model)
    except (KeyError, ValueError):
        return model


async def run(args):
    cookie_val, use_auto = resolve_cookie(args)
    model = MODEL_MAP[args.model]
    aspect = ASPECT_MAP[args.aspect]
    content_type = "video" if args.video else "image"
    timestamp = datetime.datetime.now().strftime("%y%m%d-%H%M%S")
    model_label = model_display(model)

    logger = logging.getLogger("bingart")
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
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

    print(_header(__version__, timestamp, model_label, args.aspect, content_type))
    print(_color("dim", f"  Working on it - sending your prompt to Bing..."))

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
        print()
        print(format_text(result, content_type))

    if args.download:
        print()
        await download_results(
            result, args.download, content_type, model_label, args.aspect
        )


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

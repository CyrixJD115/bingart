# bingart

bingart is an unofficial async API wrapper for Bing Image & Video Creator. It allows you to programmatically generate AI-powered images and videos using Bing's creation tools with support for multiple models and aspect ratios.

Now includes a full **command-line interface** — no scripting required.

> **Warning:** The `_U` auth cookie should be changed every 2-4 weeks for proper functionality.

## Key Features

- **CLI support** — generate images and videos directly from the terminal
- **Fully asynchronous** — built on `curl_cffi` `AsyncSession` and `asyncio`
- **Generate images** with multiple AI models (DALL-E, GPT-4O, MAI1)
- **Generate videos** from text prompts
- **Custom aspect ratios** (Square, Landscape, Portrait)
- **Get image URLs** — up to 4 generated images per request
- **Flexible authentication** via cookies or auto-fetched from browsers
- **Enhanced prompts** — get AI-improved versions of your prompts
- **Async context manager** support (`async with`)
- **Custom exceptions** for common error handling
- **Download support** — save generated images/video directly to disk

## Installation

### From PyPI

```bash
pip install bingart
```

### From Source (Portable)

```bash
git clone https://github.com/DedInc/bingart.git
cd bingart
python bingart.py --help
```

No install needed — `bingart.py` at the project root works as a portable runner.

## CLI Usage

### Basic Image Generation

```bash
bingart "sunset over mountains" -c YOUR_U_COOKIE
```

### Auto-Detect Cookie from Browser

```bash
bingart "cyberpunk city" -A
```

### Video Generation

```bash
bingart "a dancing robot in a futuristic city" -V -A
```

### All Flags

```text
usage: bingart [-h] [--version] [-m {dalle,gpt4o,mai1}]
               [-a {square,landscape,portrait}] [-V] [-c COOKIE | -A]
               [-o {text,json,urls}] [-d DIR] [-v]
               prompt

positional arguments:
  prompt                          Text prompt for image/video generation.

options:
  -h, --help                      Show help message and exit
  --version                       Print version
  -m, --model                     AI model: dalle, gpt4o, mai1 (default: dalle)
  -a, --aspect                    Aspect ratio: square, landscape, portrait (default: square)
  -V, --video                     Generate a video instead of an image
  -c, --cookie COOKIE             _U auth cookie value for Bing
  -A, --auto                      Auto-detect _U cookie from installed browsers
  -o, --output {text,json,urls}   Output format (default: text)
  -d, --download DIR              Download generated files to DIR
  -v, --verbose                   Enable verbose/debug output
```

### Models

| Flag | Model |
|------|-------|
| `-m dalle` | DALL-E 3 (default) |
| `-m gpt4o` | GPT-4O image generation |
| `-m mai1` | MAI1 model |

### Aspect Ratios

| Flag | Ratio |
|------|-------|
| `-a square` | 1:1 (default) |
| `-a landscape` | 7:4 (wide) |
| `-a portrait` | 4:7 (tall) |

### Output Formats

**Text** (default) — human-readable:

```bash
bingart "abstract art" -A
```
```text
Model: DALLE
Aspect: SQUARE
Enhanced Prompt: abstract art composition with vibrant colors
Images (4):
  [1] https://th.bing.com/th/id/OIG.xxx?pid=ImgGn
  [2] https://th.bing.com/th/id/OIG.yyy?pid=ImgGn
  [3] https://th.bing.com/th/id/OIG.zzz?pid=ImgGn
  [4] https://th.bing.com/th/id/OIG.www?pid=ImgGn
```

**JSON** — raw API response:

```bash
bingart "abstract art" -A -o json
```
```json
{
  "images": [
    {"url": "https://th.bing.com/th/id/OIG.xxx?pid=ImgGn"},
    {"url": "https://th.bing.com/th/id/OIG.yyy?pid=ImgGn"}
  ],
  "prompt": "abstract art composition",
  "model": "DALLE",
  "aspect": "SQUARE"
}
```

**URLs** — one per line, pipe-friendly:

```bash
bingart "abstract art" -A -o urls
```
```text
https://th.bing.com/th/id/OIG.xxx?pid=ImgGn
https://th.bing.com/th/id/OIG.yyy?pid=ImgGn
```

### Download Files

Save generated images or video directly to a directory:

```bash
bingart "sunset over mountains" -A -d ./output
```
```text
Model: DALLE
Aspect: SQUARE
Enhanced Prompt: sunset over mountains with golden light
Images (4):
  [1] https://th.bing.com/th/id/OIG.xxx?pid=ImgGn
  [2] https://th.bing.com/th/id/OIG.yyy?pid=ImgGn
Downloading image 1/4 -> output/001.jpg
  Saved: output/001.jpg
Downloading image 2/4 -> output/002.jpg
  Saved: output/002.jpg
```

### Authentication

Auth is resolved in this order:

1. `--cookie` / `-c` flag — pass the `_U` cookie value directly
2. `--auto` / `-A` flag — auto-detect from installed browsers (Chrome, Edge, Firefox, Brave, Opera, Vivaldi, Chromium)
3. `BINGART_COOKIE` environment variable — set it in your shell profile
4. Interactive prompt — if none of the above are provided, you'll be prompted

### Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Authentication error (invalid or expired cookie) |
| `2` | Prompt rejected (content policy violation) |
| `3` | Generic / unknown error |

### More Examples

```bash
# GPT-4O landscape image, JSON output
bingart "futuristic cityscape" -m gpt4o -a landscape -A -o json

# Portrait image, download to folder
bingart "mystical wizard portrait" -m dalle -a portrait -d ./art

# Video with auto cookie, verbose logging
bingart "cat playing piano" -V -A -v

# Pipe URLs to wget
bingart "geometric patterns" -o urls -c YOUR_COOKIE | xargs -n1 wget
```

## Python API Usage

### Basic Setup

Import and instantiate the `BingArt` class with a valid `_U` cookie value:

```python
import asyncio
from bingart import BingArt

async def main():
    bing_art = BingArt(auth_cookie_U='your_cookie_value_here')
    try:
        result = await bing_art.generate('sunset over mountains')
        print(result)
    finally:
        await bing_art.close()

asyncio.run(main())
```

### Using Async Context Manager (Recommended)

```python
import asyncio
from bingart import BingArt

async def main():
    async with BingArt(auth_cookie_U='your_cookie_value_here') as bing_art:
        result = await bing_art.generate('sunset over mountains')
        print(result)

asyncio.run(main())
```

### Auto Cookie Detection

Let bingart automatically fetch cookies from your installed browsers:

```python
from bingart import BingArt

bing_art = BingArt(auto=True)
```

Supported browsers for auto-detection:
- Chrome
- Edge
- Firefox
- Brave
- Opera
- Vivaldi
- Chromium

### Advanced Usage with Models and Aspect Ratios

```python
import asyncio
from bingart import BingArt, Model, Aspect

async def main():
    async with BingArt(auth_cookie_U='your_cookie_value') as bing_art:
        result = await bing_art.generate(
            'a futuristic cityscape',
            model=Model.GPT4O,
            aspect=Aspect.PORTRAIT
        )
        print(result)

        result = await bing_art.generate(
            'serene mountain landscape',
            model=Model.MAI1,
            aspect=Aspect.LANDSCAPE
        )
        print(result)

        result = await bing_art.generate(
            'abstract art composition',
            model=Model.DALLE,
            aspect=Aspect.SQUARE
        )
        print(result)

asyncio.run(main())
```

### Available Models

```python
from bingart import Model

Model.DALLE    # DALL-E 3 (default)
Model.GPT4O    # GPT-4O image generation
Model.MAI1     # MAI1 model
```

### Available Aspect Ratios

```python
from bingart import Aspect

Aspect.SQUARE      # 1:1 (default)
Aspect.LANDSCAPE   # 7:4 (wide)
Aspect.PORTRAIT    # 4:7 (tall)
```

### Video Generation

```python
import asyncio
from bingart import BingArt

async def main():
    async with BingArt(auth_cookie_U='your_cookie_value') as bing_art:
        result = await bing_art.generate(
            'a dancing robot in a futuristic city',
            content_type='video'
        )
        print(result)

asyncio.run(main())
```

## Output Format

### Image Generation Response

```json
{
  "images": [
    {"url": "https://th.bing.com/th/id/OIG.xxx?pid=ImgGn"},
    {"url": "https://th.bing.com/th/id/OIG.yyy?pid=ImgGn"},
    {"url": "https://th.bing.com/th/id/OIG.zzz?pid=ImgGn"},
    {"url": "https://th.bing.com/th/id/OIG.www?pid=ImgGn"}
  ],
  "prompt": "enhanced version of your original prompt",
  "model": "GPT4O",
  "aspect": "PORTRAIT"
}
```

### Video Generation Response

```json
{
  "video": {
    "video_url": "https://..."
  },
  "prompt": "your original prompt"
}
```

## Exception Handling

```python
import asyncio
from bingart import BingArt, AuthCookieError, PromptRejectedError

async def main():
    try:
        async with BingArt(auth_cookie_U='your_cookie_value') as bing_art:
            result = await bing_art.generate('your prompt here')
            print(result)
    except AuthCookieError:
        print("Invalid authentication cookie or session expired")
    except PromptRejectedError:
        print("Prompt was rejected due to content policy violation")

asyncio.run(main())
```

### Available Exceptions

- `AuthCookieError`: Raised when authentication cookie is invalid or expired
- `PromptRejectedError`: Raised when prompt violates content policy or is rejected as unethical

## Getting Your Cookie

1. Open your browser and go to [Bing Image Creator](https://www.bing.com/images/create)
2. Log in with your Microsoft account
3. Open Developer Tools (F12)
4. Go to Application/Storage → Cookies → `https://www.bing.com`
5. Find the `_U` cookie and copy its value

## Requirements

- Python >= 3.6
- curl_cffi
- rookiepy

## Contributing

Pull requests are welcome! Please open an issue to discuss major changes before submitting.

## License

MIT License - see LICENSE file for details.

## Disclaimer

This is an unofficial API wrapper and is not affiliated with Microsoft or Bing. Use responsibly and in accordance with Bing's terms of service.
